#!/usr/bin/env python

from pyorbital.orbital import Orbital
from pyorbital import astronomy
from datetime import datetime
import urllib2
import time
import math
import re
import os.path

OBS_LAT = 51.05
OBS_LON = 3.7
OBS_ALT = 36

class TLEData:
    SOURCES = ['amateur.txt', 'cubesat.txt', 'stations.txt', 'weather.txt']
    BASEURL = r'http://celestrak.com/NORAD/elements/'
    SATSURL = r'http://www.ne.jp/asahi/hamradio/je9pel/satslist.csv'

    RX_SATNAME = re.compile(r'(.*) \((.*)\)')

    TLE_DB  = 'tle.db'
    SAT_DB  = 'sat.db'
    FIX_DB  = 'namefix.db'

    D2R = math.pi / 180
    R2D = 180 / math.pi

    def __init__(self):
        self.orbByID = dict()
        self.satByID = dict()
        
        if not os.path.isfile(self.TLE_DB):
            self.updateAllTLE()
            
        if not os.path.isfile(self.SAT_DB):
            self.updateAllSat()
            
        self.loadAll()

    def updateAllTLE(self):
        tleData = list()
        for source in self.SOURCES:
            url = self.BASEURL + source
            response = urllib2.urlopen(url)
            while response:
                header = response.readline().rstrip()
                if not header: break
                line1  = response.readline().rstrip()
                line2  = response.readline().rstrip()
                # append by 3 lines
                tleData.append(header)
                tleData.append(line1)
                tleData.append(line2)
        with open(self.TLE_DB, 'w') as fileOut:
            for line in tleData:
                fileOut.write('%s\n' % line)

    def updateAllSat(self):
        satData = list()
        url = self.SATSURL
        response = urllib2.urlopen(url)
        for line in response:
            line = line.rstrip()
            satData.append(line)
        with open(self.SAT_DB, 'w') as fileOut:
            for line in satData:
                fileOut.write('%s\n' % line)        
            
    def loadAll(self):
        with open(self.TLE_DB, 'r') as dbFile:
            while dbFile:
                header = dbFile.readline().rstrip()
                if not header: break
                line1  = dbFile.readline().rstrip()
                line2  = dbFile.readline().rstrip()
                name = header
                try:
                    orb = Orbital(name, line1 = line1, line2 = line2)
                    satID = orb.tle.satnumber
                    self.orbByID[satID] = orb
                except:
                    print "Failed to create TLE for", name

        nameFix = dict()
        try:
            with open(self.FIX_DB, 'r') as dbFile:
                for line in dbFile:
                    line = line.rstrip()
                    fields = line.split(',')
                    if len(fields) == 2:
                        nameFix[fields[0]] = fields[1]
        except:
            pass

        with open(self.SAT_DB, 'r') as dbFile:
            for line in dbFile:
                line = line.rstrip()
                fields = line.split(';')
                name = fields[0]
                satID = fields[1]
                uplink = fields[2].rstrip()
                downlink = fields[3].rstrip()
                beacon = fields[4].rstrip()
                mode = fields[5].rstrip()
                status = fields[7].rstrip()
                
                if not satID:
                    print "Ignoring", name, satID, status
                    #if status == 'active' or status == 'Operational':
                        #print name, name in self.orbByName
                        #if name in nameFix:
                        #    name = nameFix[name]
                        #    print name                        
                else:
                    self.satByID[satID] = (uplink, downlink, beacon, mode, status, name)
                    
        self.satIDs = set(self.orbByID.keys()) & set(self.satByID.keys())
        #print len(self.orbByID.keys())
        #print len(self.satByID.keys())
        #print len(self.satIDs)
        
        #missing = set(self.satByID.keys()) - set(self.orbByID.keys())
        #missingNames = [self.satByID[x][5] + ': ' + self.satByID[x][4] for x in missing]
        #print '\n'.join(missingNames)

    def getSatellites(self):
        #return self.orbByID.keys()
        return self.satIDs
        
    def getName(self, satID):
        return self.orbByID[satID].satellite_name

    def getSatInfo(self, satID):
        if satID in self.satByID:
            return self.satByID[satID]
        return None

    def getAzimElev(self, satID, time, lat, lon, alt):
        return self.orbByID[satID].get_observer_look(time, lon, lat, alt)
        
    def getDistance(self, satID, time, lat, lon, alt):
        (lon2, lat2, alt2) = self.orbByID[satID].get_lonlatalt(time)
        
        (pos_x, pos_y, pos_z), (vel_x, vel_y, vel_z) = astronomy.observer_position(
                time, lon2, lat2, alt2)

        (opos_x, opos_y, opos_z), (ovel_x, ovel_y, ovel_z) = \
            astronomy.observer_position(time, lon, lat, alt)

        rx = pos_x - opos_x
        ry = pos_y - opos_y
        rz = pos_z - opos_z
        
        r = math.sqrt(rx*rx + ry*ry + rz*rz)
        return (alt2, r)
    
    def parseEntry(self, header):
        m1 = self.RX_SATNAME.match(header)
        if m1:
            name = m1.group(1)
            nameShort = m1.group(2)
        else:
            name = header
            nameShort = name
        return (name, nameShort)
    
AZIM = 'N NE E SE S SW W NW'.split()   
def simpleAzim(angle):
    division = 360.0 / len(AZIM)
    part = angle / division
    part = int(part + 0.5) % len(AZIM)
    return AZIM[part]

def main():
    orbData = TLEData()
        
    while True:   
        # calculate current satellite data
        visible = list()
        now = datetime.utcnow()
        for satID in orbData.getSatellites():
            try:
                (azim, elev) = orbData.getAzimElev(satID, now, OBS_LAT, OBS_LON, OBS_ALT)
                if elev > 0:
                    (alt, dist) = orbData.getDistance(satID, now, OBS_LAT, OBS_LON, OBS_ALT)
                    visible.append((satID, azim, elev, dist, alt))
            except NotImplementedError:
                pass

        # update display
        print("\x1b[H\x1b[2J")     
        print "%3s %-25s %7s %4s %7s %-25s" % ('#', 'Name', 'Azim', 'Elev', 'Dist', 'Comm')
        print "-----------------------------------------------------------------------------------------------"
        row = 1   
        for (satID, azim, elev, dist, alt) in sorted(visible, key = lambda x: x[2], reverse=True):
            name = orbData.getName(satID)
            comm = orbData.getSatInfo(satID)
            (up, down, beacon, mode, status, name2) = comm
            if status != 'active' and status != 'Operational':
                continue
            commList = list()
            #commList.append(status)
            if up: commList.append('U[%s]' % up)
            if down: commList.append('D[%s]' % down)
            if beacon: commList.append('B[%s]' % beacon)
            if mode: commList.append('M[%s]' % mode)
            comm = ' '.join(commList)
            print "%3d %-25s %4.0f %2s %4.0f %7.0f %-25s" % (row, name, azim, simpleAzim(azim), elev, dist, comm)
            row += 1
        print "-----------------------------------------------------------------------------------------------"
        row = 1   
        for (satID, azim, elev, dist, alt) in sorted(visible, key = lambda x: x[2], reverse=True):
            name = orbData.getName(satID)
            comm = orbData.getSatInfo(satID)
            (up, down, beacon, mode, status, name2) = comm
            if status == 'active' or status == 'Operational':
                continue
            commList = list()
            commList.append(status)
            #if up: commList.append('U[%s]' % up)
            #if down: commList.append('D[%s]' % down)
            #if beacon: commList.append('B[%s]' % beacon)
            #if mode: commList.append('M[%s]' % mode)
            comm = ' '.join(commList)
            print "%3d %-25s %4.0f %2s %4.0f %7.0f %-25s" % (row, name, azim, simpleAzim(azim), elev, dist, comm)
            row += 1
            
        print 
        # sleep
        time.sleep(1)
    
if __name__ == '__main__':
    main()
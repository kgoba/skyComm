#!/usr/bin/env python

from pyorbital.orbital import Orbital
from pyorbital import astronomy

from datetime import datetime
import argparse
import urllib2
import time
import math
import sys
import re
import os.path

OBS_LAT = 51.05
OBS_LON = 3.7
OBS_ALT = 36
OBS_HORIZON = 5

# maximum age of TLE data, in seconds
MAX_TLE_AGE = 3600

# maximum age of satellite data, in seconds
MAX_SAT_AGE = 3600*24

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
        
        self.updateAllTLE()            
        self.updateAllSat()
            
        self.loadAll()

    def updateAllTLE(self):
        if os.path.isfile(self.TLE_DB):
            modified = datetime.fromtimestamp(os.path.getmtime(self.TLE_DB))
            age = datetime.utcnow() - modified
            if age.total_seconds() < MAX_TLE_AGE:
                return

        print "Downloading TLE data..."
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
        if os.path.isfile(self.SAT_DB):
            modified = datetime.fromtimestamp(os.path.getmtime(self.SAT_DB))
            age = datetime.utcnow() - modified
            if age.total_seconds() < MAX_SAT_AGE:
                return

        print "Downloading satellite comm data..."
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
                    #print "Failed to create TLE for", name
                    pass

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
                    #print "Ignoring", name, satID, status
                    #if status == 'active' or status == 'Operational':
                        #print name, name in self.orbByName
                        #if name in nameFix:
                        #    name = nameFix[name]
                        #    print name                        
                    pass
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

    def getNextPasses(self, satID, time, length, lat, lon, alt):
        return self.orbByID[satID].get_next_passes(time, length, lon, lat, alt)

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
        
        vx = vel_x - ovel_x
        vy = vel_y - ovel_y
        vz = vel_z - ovel_z
        
        r = math.sqrt(rx*rx + ry*ry + rz*rz)
        v = math.sqrt(vx*vx + vy*vy + vz*vz)
        return (alt2, r, v)
    
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

def liveTrack(args, orbData):
    # calculate current satellite data
    visible = list()
    now = datetime.utcnow()
    for satID in orbData.getSatellites():
        try:
            (azim, elev) = orbData.getAzimElev(satID, now, args.lat, args.lon, args.alt)
            if elev < args.horizon:
                continue
            (alt, dist, vel) = orbData.getDistance(satID, now, args.lat, args.lon, args.alt)
            visible.append((satID, azim, elev, dist, vel, alt))
        except NotImplementedError:
            pass

    # clear display
    sys.stdout.write("\x1b[H\x1b[2J")
    
    # update display
    print "%3s %-25s %7s %4s %7s %-32s [%8s]" % ('#', 'Name', 'Azim', 'Elev', 'Dist', 'Comm', now.strftime('%H:%M:%S'))
    print "---------------------------------------------------------------------------------[ACTIVE SATS]" 
    row = 1   
    for (satID, azim, elev, dist, vel, alt) in sorted(visible, key = lambda x: x[2], reverse=True):
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
        
    print

    print "---------------------------------------------------------------------------------[OTHER  SATS]"
    row = 1   
    for (satID, azim, elev, dist, vel, alt) in sorted(visible, key = lambda x: x[2], reverse=True):
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

def predict(args, orbData):
    now = datetime.utcnow()
    passList = list()
    for satID in orbData.getSatellites():
        passes = orbData.getNextPasses(satID, now, args.hours, args.lat, args.lon, args.alt)
        for (time_rise, time_set, time_max) in passes:
            (azim, elev) = orbData.getAzimElev(satID, time_max, args.lat, args.lon, args.alt)
            if elev < args.horizon:
                continue
            (alt, dist, vel) = orbData.getDistance(satID, time_max, args.lat, args.lon, args.alt)
            passList.append((satID, time_max, azim, elev, dist))
            
    row = 1
    for (satID, time_max, azim, elev, dist) in sorted(passList, key = lambda x: -x[3]):
        name = orbData.getName(satID)
        fromNow = time_max - now
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
        print "%3d %-25s %4.0f %3.0f %5.0f %9s (%3.0f min) %s" % (row, name, azim, elev, dist, time_max.strftime('%H:%M:%S'), fromNow.total_seconds()/60, comm)
        row += 1
        #print row, satID, passes

def main(args):
    orbData = TLEData()
    
    if args.command == 'track':
        try:
            while True:
                liveTrack(args, orbData)
                # sleep
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit()
    elif args.command == 'predict':
        predict(args, orbData)
    
if __name__ == '__main__':    
    parser = argparse.ArgumentParser(description='Track the amateur satellites in orbit')
    parser.add_argument('command', choices=['track', 'predict'], default='track', nargs='?', help='Action: either track live positions or predict next passes')
    parser.add_argument('--lat', type=float, default=OBS_LAT, help='Observer latitude (degrees floating point)')
    parser.add_argument('--lon', type=float, default=OBS_LON, help='Observer longitude (degrees floating point)')
    parser.add_argument('--alt', type=float, default=OBS_ALT, help='Observer altitude (meters)')
    parser.add_argument('--horizon', type=float, default=OBS_HORIZON, help='Horizon elevation (degrees)')
    parser.add_argument('--hours', type=float, default=1, help='Prediction window (in hours)')
    parser.add_argument('--sort', choices=['elev', 'time', 'name'], default='elev', nargs='?', help='Sorting key')

    args = parser.parse_args()
    main(args)

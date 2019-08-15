#!/usr/bin/env python

from pyorbital.orbital import Orbital
from pyorbital import astronomy
from texttable import Texttable

from datetime import datetime, timedelta
import argparse
import urllib2
import time
import math
import sys
import re
import os.path

OBS_LAT = 56.95
OBS_LON = 24.1
OBS_ALT = 36
OBS_HORIZON = 5

# maximum age of TLE data, in seconds
MAX_TLE_AGE = 3600*8

# maximum age of satellite data, in seconds
MAX_SAT_AGE = 3600*24

# short names of 8 cardinal directions
AZIM = 'N NE E SE S SW W NW'.split()

class TLEData:
    SOURCES = ['amateur.txt', 'cubesat.txt', 'stations.txt', 'weather.txt', 
               'tle-new.txt', 'satnogs.txt', 'science.txt', 'resource.txt', 
               'geo.txt']
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
        # Check existing local file
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
        # read satellite TLE data and store by satellite ID
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
                except Exception as e:
                    #print "Failed to create TLE for", name, '(%s)' % str(e)
                    pass

        # read satellite communication parameters
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
                
                if satID:
                    self.satByID[satID] = (uplink, downlink, beacon, mode, status, name)
                #else:
                    #print "Ignoring", name, satID, status
                    #if status == 'active' or status == 'Operational':
                        #print name, name in self.orbByName
                        #if name in nameFix:
                        #    name = nameFix[name]
                        #    print name                        
                    
        # Intersection of satellites with TLE info and comms info
        self.satIDs = set(self.orbByID.keys()) # & set(self.satByID.keys())
        #missing = set(self.satByID.keys()) - set(self.orbByID.keys())
        #print ', '.join(sorted([self.orbByID[x].satellite_name for x in self.satIDs]))
        return

    def getSatellites(self):
        #return self.orbByID.keys()
        return self.satIDs
        
    def getName(self, satID):
        return self.orbByID[satID].satellite_name

    def getSatInfo(self, satID):
        if satID in self.satByID:
            return self.satByID[satID]
        return ('', '', '', '', '---', self.getName(satID))

    def getNextPasses(self, satID, time, length, lat, lon, alt):
        return self.orbByID[satID].get_next_passes(time, length, lon, lat, alt)

    def getAzimElev(self, satID, time, lat, lon, alt):
        return self.orbByID[satID].get_observer_look(time, lon, lat, alt)
        
    def getMaxElev(self, satID, time, lat, lon, alt):
        sat = self.orbByID[satID]
        minutes = [0.1 * x for x in range(80)]
        elev = [sat.get_observer_look(time + timedelta(minutes=x), lon, lat, alt)[1] for x in minutes]
        return max(elev)
        
    def getDistance(self, satID, time, lat, lon, alt):
        # Get satellite position (lat/lon/altitude)
        (lon2, lat2, alt2) = self.orbByID[satID].get_lonlatalt(time)
        
        (pos_x, pos_y, pos_z), (vel_x, vel_y, vel_z) = \
            self.orbByID[satID].get_position(time, normalize=False)

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
        v_r = (rx*vx + ry*vy + rz*vz) / (r) # Radial projection

        return (alt2, r, v, v_r)
    
    def parseEntry(self, header):
        m1 = self.RX_SATNAME.match(header)
        if m1:
            name = m1.group(1)
            nameShort = m1.group(2)
        else:
            name = header
            nameShort = name
        return (name, nameShort)


def simpleAzim(angle):
    division = 360.0 / len(AZIM)
    part = angle / division
    part = int(part + 0.5) % len(AZIM)
    return AZIM[part]


def liveTrack(args, orbData):
    if args.id is None:
        track_ids = orbData.getSatellites()
    else:
        track_ids = [args.id]
    # calculate current satellite data
    visible = list()
    now = datetime.utcnow()
    for satID in track_ids:
        try:
            (azim, elev) = orbData.getAzimElev(satID, now, args.lat, args.lon, args.alt)
            # Check if satellite below visibility horizon
            if args.id is None and elev < args.horizon:
                continue
            (alt, dist, vel, vel_r) = orbData.getDistance(satID, now, args.lat, args.lon, args.alt)
            elev_max = orbData.getMaxElev(satID, now, args.lat, args.lon, args.alt)
            visible.append({
                'satID' : satID,
                'azim'  : azim,
                'elev'  : elev,
                'dist'  : dist,
                'vel'   : vel,
                'vel_r' : vel_r,
                'elev_max': elev_max,
                'alt'   : alt
            })
        except NotImplementedError:
            pass

    # clear display
    sys.stdout.write("\x1b[H\x1b[2J")
    
    # update display
    print "%3s %-25s %7s %4s %7s %-28s [%8s UTC]" % ('#', 'Name', 'Azim', 'Elev', 'Dist', 'Comm', now.strftime('%H:%M:%S'))
    print "[ACTIVE SATS]---------------------------------------------------------------------------------" 
    table = Texttable()
    table.set_deco(0)
    table.set_max_width(0)
    table.header('# Name Azim Elev Dist Vel Comm'.split())
    table.set_header_align('r l r r r r l'.split())
    table.set_cols_align  ('r l r r r r l'.split())
    table.set_cols_dtype  ('t t t t t t t'.split())
    row = 1   
    for entry in sorted(visible, key = lambda x: x['elev'], reverse=True):
        satID, azim, elev, dist, vel, vel_r = [entry[x] for x in 'satID azim elev dist vel vel_r'.split()]

        name = orbData.getName(satID)
        comm = orbData.getSatInfo(satID)
        (up, down, beacon, mode, status, name2) = comm
        if status != 'active' and status != 'Operational':
            continue
        commList = list()
        if down: commList.append('D[%s]' % down)
        if up:   commList.append('U[%s]' % up)
        if beacon: commList.append('B[%s]' % beacon)
        if mode: commList.append('%s' % mode)
        comm = ' '.join(commList)
        table.add_row(("%d|%s|%.0f|%.0f|%.0f|%.2f|%s" % (row, name, azim, elev, dist, vel_r, comm)).split('|'))
        row += 1
    
    print table.draw()
    print

    print "[OTHER  SATS]---------------------------------------------------------------------------------"
    table = Texttable()
    table.set_deco(0)
    table.set_max_width(0)
    table.header('# Name Azim Elev Dist Vel Comm'.split())
    table.set_header_align('r l r r r r l'.split())
    table.set_cols_align  ('r l r r r r l'.split())
    table.set_cols_dtype  ('t t t t t t t'.split())
    row = 1   
    for entry in sorted(visible, key = lambda x: x['elev'], reverse=True)[:10]:
        satID, azim, elev, dist, vel_r = [entry[x] for x in 'satID azim elev dist vel_r'.split()]
        name = orbData.getName(satID)
        comm = orbData.getSatInfo(satID)
        (up, down, beacon, mode, status, name2) = comm
        if status == 'active' or status == 'Operational':
            continue
        commList = list()
        commList.append(status)
        comm = ' '.join(commList)
        table.add_row(("%d|%s|%.0f|%.0f|%.0f|%.2f|%s" % (row, name, azim, elev, dist, vel_r, comm)).split('|'))
        row += 1
    print table.draw()


def predict(args, orbData):
    now = datetime.utcnow()
    passList = list()
    for satID in orbData.getSatellites():
        passes = orbData.getNextPasses(satID, now, int(args.hours), args.lat, args.lon, args.alt)
        for (time_rise, time_set, time_max) in passes:
            (azim, elev) = orbData.getAzimElev(satID, time_max, args.lat, args.lon, args.alt)
            if elev < args.horizon:
                continue
            (alt, dist, vel) = orbData.getDistance(satID, time_max, args.lat, args.lon, args.alt)
            passList.append((satID, time_max, azim, elev, dist))
            
    print "%3s %-25s %7s %3s %5s %18s %s" % ('#', 'Name', 'Azim', 'Elev', 'Dist', 'Max. elevation', 'Comm')
    print "[PREDICTION]-------------------------------------------------------------------------------" 
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
        if down: commList.append('D[%s]' % down)
        if up: commList.append('U[%s]' % up)
        if beacon: commList.append('B[%s]' % beacon)
        if mode: commList.append('%s' % mode)
        comm = ' '.join(commList)
        print "%3d %-25s %4.0f %2s %3.0f %5.0f %9s (%3.0f min) %s" % (row, name, azim, simpleAzim(azim), elev, dist, time_max.strftime('%H:%M:%S'), fromNow.total_seconds()/60, comm)
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
    parser.add_argument('command', choices=['track', 'predict'], default='track', nargs='?', 
                        help='Action: either track live positions (default) or predict next passes')
    parser.add_argument('--lat', type=float, default=OBS_LAT, help='Observer latitude (degrees floating point)')
    parser.add_argument('--lon', type=float, default=OBS_LON, help='Observer longitude (degrees floating point)')
    parser.add_argument('--alt', type=float, default=OBS_ALT, help='Observer altitude (meters)')
    parser.add_argument('--horizon', type=float, default=OBS_HORIZON, 
                        help='Horizon elevation (degrees), default %.0f degrees' % OBS_HORIZON)
    parser.add_argument('--hours', type=float, default=1, help='Prediction window (in hours), default 1 hour')
    parser.add_argument('--sort', choices=['elev', 'time', 'name'], default='elev', nargs='?', help='Sorting key (default: elevation)')
    parser.add_argument('--id', type=str, default=None, help='Track specific satellite ID')

    args = parser.parse_args()
    main(args)

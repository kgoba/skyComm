# skyComm --- track amateur satellites

`skyComm` allows live tracking of amateur satellites as well as prediction of next passes. `skyComm` tells you the azimuth, elevation, and distance to the satellite, as well as its communication parameters (uplink, downlink and beacon frequencies, modulation type, etc).

The list of active satellite and their frequencies is collected from the website of Mineo Wakita JE9PEL (http://www.ne.jp/asahi/hamradio/je9pel/satslist.htm).

The orbital parameters are obtained from another excellent website, CelesTrack (https://www.celestrak.com/NORAD/elements/). 

## Installation

Currently there are no installation scripts. Before you run `skyComm`, install the necessary prerequisites by running
```bash
sudo -H pip install -r requirements.txt
```

Then you should be able to run `track.py` from the main directory. 

## Usage

For a list of command line arguments, run
```bash
./track.py -h
```

For example, to predict passes for the next hour over Riga, Latvia (above 5 degrees of horizon), run the following:
```bash
./track.py --lat 56.9 --lon 24.1 predict
```

To monitor live satellite positions as viewed from Riga, Latvia, use the following:
```bash
./track.py --lat 56.9 --lon 24.1
```


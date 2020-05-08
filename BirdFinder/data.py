import init
import ebird

import logging
from enum import Enum
import os, os.path
import csv, json

# turn on logging
log = init.get_module_logger(__name__)

def getFullPathToFile(filename:str) -> str:
    script_path = os.path.abspath(__file__) # i.e. /path/to/dir/foobar.py
    script_dir = os.path.split(script_path)[0] #i.e. /path/to/dir/ 
    abs_file_path = os.path.join(script_dir, filename)
    return abs_file_path

def getRegionFileName(region: str) -> str:
    assert len(region) == 5, "Region should be 5 characters long" 
    filename = "data\\ebird_{}__2000_2020_1_12_barchart.txt".format(region)
    return getFullPathToFile(filename)

#Check if our datafile exists, and if so, is it newer than all the source data files.
#Return True if it exists and is newer than all source data, else False
def checkRegionDataFileValid(filename: str) -> bool:
    result = True

    try:
        #check that it is newer than each data file
        datalastmodified = os.path.getmtime(filename)

    except FileNotFoundError:
        log.info("Data file doesn't exist")
        result = False
    
    except:
        log.info("Some other error. What went wrong, I wonder?")
        result = False
    
    else:
        for r in init.regions:
            sourcelastmodified = os.path.getmtime(getRegionFileName(r))
            if datalastmodified <= sourcelastmodified:
                log.info("Source data is newer than data file")
                result = False
                break

    return result


#Check if our datafile has valid contents, meaning all the top-level nodes are states and
#all the second level nodes are birds. Return True if so, else False
def checkRegionDataFileContents(regiondata: dict, ebirdtaxonomy : dict) -> bool:
    result = True
    
    try: 
        if len(regiondata) == 0:
            log.debug("File contents not valid: empty")
            raise

        for r in regiondata:
            #if currently in our list of valid places
            if r in init.regions:
                #check that each bird is in the taxonomy, and has a valid status
                if len(regiondata[r]) > 0:
                    for b in regiondata[r]:
                        if not(b in ebirdtaxonomy and regiondata[r][b] in init.birdstatus):
                            log.debug("File contents not valid at {} : {}".format(b, regiondata[r][b]))
                            raise
                else:
                    log.debug("File contents not valid: no birds in {}".format(r))
                    raise
            else:
                log.debug("File contents not valid: {} not a region".format(r))
                raise

    except: #if anything above goes wrong, like file was empty, then just fail
        result = False
    
    return result


#returns a dict of the form { "bird" : [List of 48 week datas as float] } for a single state
def loadRegion(r : str, ebirdtaxononmy : dict) -> dict:
    regiondata = {}
    with open(getRegionFileName(r), encoding='utf8') as tabfile:
        i = 0
        for row in csv.reader(tabfile, delimiter="\t"):
            #skip first 16 lines of the file to get to the first bird
            if i <= 15:
                i += 1
            else:
                if len(row) > 0:        #the last row and possibly others could be blank
                    bird = row.pop(0)   #first cell is always the bird name
                    
                    #check that we have an actual species before adding it to our database
                    #the ebird data has things like, "bird sp." and other data we don't want
                    if ebird.isValid(ebirdtaxononmy[bird]):
                        x = row.pop(48)     #for some reason they add a last column
                        frequencies = [float(x) for x in row] #make a list out of the row, converting to float
                        regiondata[bird] = frequencies
    return regiondata

#Summarize all the columnar data into something useful
def summarizeRegion(regiondata : dict) -> dict:
    #COMMON = If a bird is reported on at least 10% of checklists for 36 weeks of the year
    #UNUSUAL = If a bird is reported  on at least 2% of checklists for 36 weeks
    #SEASONAL = If a bird is reported on at least 2% of checklists for 12 weeks
    #LOCALIZED = None of the above, but reported on at least 0.5% of checklists for 24 weeks
    #RARE = Seen on 0.01% of checklists but at least 16 weeks
    #VAGRANT = the rest

    frequencydata = ( (init.birdstatus[1], 0.10 ,  36), 
                      (init.birdstatus[2], 0.02,   36),
                      (init.birdstatus[3], 0.02,   12),
                      (init.birdstatus[4], 0.005,  24),
                      (init.birdstatus[5], 0.0001, 16),
                      (init.birdstatus[6], 0,       0) )
    summary = {}

    for bird in regiondata:
        for status in frequencydata:
            weeks = len([freq for freq in regiondata[bird] if freq > status[1]])
            if weeks > status[2]:
                summary[bird] = status[0]
                break

    return summary

#open region file and parse it. 
#return a dictionary of dictionaries, where the key 
def loadAllRegionData(ebirdtaxonomy : dict) -> dict:
    
    data = {}
    datafile = "regiondata.json"

    #Verify that we have saved region data, and it's newer than all the data file.
    try:
        log.info("Attempting to open old data file")
        if checkRegionDataFileValid(datafile):
            with open(datafile, 'r') as openfile: 
                data = json.load(openfile)
                #TODO how to validate that the data file is properly structured?
                if not(checkRegionDataFileContents(data, ebirdtaxonomy)):
                    raise
        else:
            raise
    
    except:
        log.info("Creating data from scratch")
        #If the data file didn't exist, or was older than the source data, or couldn't be
        #opened for whatever reason, then we ignore it and create it from scratch.
        for r in init.regions:
            regiondata = loadRegion(r, ebirdtaxonomy)
            data[r] = summarizeRegion(regiondata)

        #we created the file, now save for next time
        try:
            with open(datafile, 'w') as outfile:
                json.dump(data, outfile, sort_keys = True, indent = 4, ensure_ascii = False)
        except:
            #if it can't be saved, no problem, we'll recreate it next time
            log.info("Failed to write region datafile")


    return data
import init
import logging
from enum import Enum
import os
import csv

# turn on logging
log = init.get_module_logger(__name__)

#get file name
def getFileName(region:str) -> str:
    assert len(region) == 5, "Region should be 5 characters long" 
    file = "data\\ebird_{}__2000_2020_1_12_barchart.txt".format(region)
    script_path = os.path.abspath(__file__) # i.e. /path/to/dir/foobar.py
    script_dir = os.path.split(script_path)[0] #i.e. /path/to/dir/ 
    abs_file_path = os.path.join(script_dir, file)
    return abs_file_path

#open region file and parse it. region should 5 letters, like "US-TX"
def loadRegionData(region:str) -> dict:

    data = {}

    f = getFileName(region)
    with open(f, encoding='utf8') as tabfile:
        i = 0
        for row in csv.reader(tabfile, delimiter="\t"):
            #skip first 16 lines of the file to get to the first bird
            if i <= 15:
                i += 1

            else:
                if len(row) > 0:        #the last row and possibly others could be blank
                    bird = row.pop(0)   #first cell is always the bird name
                    x = row.pop(48)     #for some reason they add a last column
                    frequencies = []
                    frequencies.append([float(x) for x in row]) #make a list out of the row, converting to float
                    data[bird] = frequencies          
    
    f.close()

    return data
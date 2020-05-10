# Set of helper functions for dealing with eBird data
import init
import logging
from enum import Enum

#for working with JSON and parsing
import urllib.request as request
import json

#ebird access key
key="jvrdn0c915eh"

# turn on logging
log = init.get_module_logger(__name__)

#TODO Reduce the taxonomy list so it only includes species?
#The dictionary will have the following format:
#   Key: A tuple of (Common name, Banding code)
#   Value: A list of everything else
def getEbirdTaxonomyDict(filename: str) -> dict:
    import csv
    
    log.info("Starting to load taxonomy")
    result = {}

    with open(filename, encoding='utf8') as csvfile:
        eBirdTaxonomyFileReader = csv.DictReader(csvfile)
        
        for row in eBirdTaxonomyFileReader:
            #Pop the common name out of the list to use as the key
            key = row.pop("COMMON_NAME")
            #TODO Someday may want to check to see if key exists, but currently it would be unique:
            #if key in result:
            
            #Add the row to our dictionary
            result[key] = row

    csvfile.close()

    log.info("Ending loading taxonomy")
    return result

# function to test whether a particular common name is a species or not (i.e. subspecies)
def isValid(ebirdentry: dict) -> bool:
    log.debug("Checking whether {} is a species".format(init.EBirdDictColumns.SCIENTIFIC_NAME.value))

    if ebirdentry[init.EBirdDictColumns.CATEGORY.value] == init.Category.SPECIES.value or ebirdentry[init.EBirdDictColumns.CATEGORY.value] == init.Category.ISSF.value:
        log.debug("Yes")
        return True

    log.debug("No")
    return False

#take the ebird dict and split the keys into a new dict of {name : code} to make lookups fast
def getBirdName(ebirddict: dict) -> dict:
    
    log.info("Making name-to-code lookup dictionary")
    result = {}

    for b in ebirddict:
        result[b[0]] = b[1]

    return result

#General function that takes a URL and requests data from it
def getListFromURL(URL: str) -> list:
    log.debug("Requesting from: {}".format(URL))
    result = []
    
    #TODO Add more error handling for other response codes
    with request.urlopen(URL) as response:
        if response.getcode() == 200:
            source = response.read()
            result = json.loads(source)
        else:
            log.critical("Error occurred while attempting to retrieve data from the API.")

    return result

#Get recent sightings
#returns: 
#  empty list == an error occurred
#  else, response from ebird, which will be a list of dictionaries
def getSightingsForLocation(lat: float, long:float, daysback:int, distKM:int) -> list:
    log.info("Get list of sightings")

    URL = "https://api.ebird.org/v2/data/obs/geo/recent?key={}&lat={}&lng={}&back={}&dist={}".format(key, lat, long, daysback, distKM)

    sightings = []
    sightings = getListFromURL(URL)

    return sightings

#Get recent places where a bird was seen 
#returns: 
#  empty list == an error occurred
#  else, response from ebird, which will be a list of dictionaries
def getLocationsForBird(lat: float, long:float, daysback:int, distKM:int, code: str) -> list:
    log.info("Get list of locations for {}".format(code))

    URL = "https://api.ebird.org/v2/data/obs/geo/recent/{}?key={}&lat={}&lng={}&back={}&dist={}".format(code, key, lat, long, daysback, distKM)
    
    places = []
    places = getListFromURL(URL)
    return places

#Returns a list of sightings of valid species/ISSF only
def filterSpecies(sightings: list, ebirdtaxonomy: dict) -> list:
    results = []
    for bird in sightings:
        if isValid(ebirdtaxonomy[(bird["comName"])]):
            results.append(bird)

    return results
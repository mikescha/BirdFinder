import json
import csv
import sys
import logging
from enum import Enum

import ebird
import init
import data

class ListType(Enum):
    LIFE = 1  #want to find birds never seen, no matter the place
    YEAR = 2  #want to find birds not seen during the current year, no matter the place
    STATELIFE = 3 #want to find birds never seen in the current state
    STATEYEAR = 4 #want to find birds never seen in the current state during the current year

#Loads the life list from a file
def getNALifeDict(filename: str, ebirdtaxonomydict: dict) -> dict:
# Assumes life list file is in the format you get from downloading all your ebird data:
#
# [ Submission ID, Common Name, Scientific Name, Taxonomic, Count, State/Province, County ...]
# or
# [ Row #, Species, Count, Location, S/P... ]
#
# Life list dictionary is the following format:
#     {  Key = bird name,  Value = Dict of { Key = state/prov, Value = set of years where bird was seen  } }
# 
# Also, this trims the list to birds seen in NA only! It excludes everything outside of 
# the Lower 48, Canada, and Alaska.

    log.info("Starting to get life list dictionary")
    lifedict = {}

    log.debug("Opening file {}".format(filename))
    with open(filename, encoding='utf8') as csvfile:
        lifelistreader = csv.reader(csvfile)
        
        #Get header row and validate that the format is expected
        row = next(lifelistreader)
        if row[1] == "Common Name" and row[5] == "State/Province":
            log.info("Found list in form of life list")
            namecolumn = 1
            placecolumn = 5
            
        elif row[1] == "Species" and row[4] == "S/P":
            log.info("Found list in form of year list")
            namecolumn = 1
            placecolumn = 4
            
        else:
            log.critical("Major problem, life list file has unexpected column names")
            return False

        for row in lifelistreader:
            bird = row[namecolumn]
            place = row[placecolumn]
            log.debug("Checking {} {}".format(bird, place))

            #date seen is always in the 12th column, and the year is always the first four characters
            year = row[11][0 : 4]

            # Skip birds seen outside north america
            if not(place[0:2] == "US" or place[0:2] == "CA") or place == "US-HI":
                log.debug("Bird {} seen outside the country or in HI. Skipping.".format(place))

            # Is the bird in the life list
            elif bird in lifedict:
                # It was, check to see if the state is in the list of states for that bird
                if place in lifedict[row[1]]:
                    log.debug("Bird {} in life list, and seen in this state. Add year if needed.".format(bird))
                    lifedict[bird][place].add(year)
                else:
                    log.debug("Bird {} in life list, and NOT seen in this state. Add state.".format(bird))
                    lifedict[bird][place] = {year}
                    
            else:
                #bird is not in lifelist
                log.debug("Bird {} NOT in life list.".format(bird))
                
                if ebird.isValid(ebirdtaxonomydict[(bird)]):
                    log.debug("Is a species, so adding.")
                    lifedict[bird] = {place : {year}}
                else:
                    log.debug("Not adding because it is not a species")
    csvfile.close()

    log.info("Number of records: {}".format(len(lifedict)))

    return lifedict

#Get list of birds we need to see
def getNeedsList(finding: ListType, state: str, sightings: list, lifedict: dict) -> list:
    log.info("Get list of birds we need")
    needs = []

    for b in sightings:
        if b["comName"] in lifedict:
            sawit = False
            #For STATE list, just need to look up whether the current state is in the for this bird or not
            if finding == ListType.STATELIFE:
                if state in lifedict[b["comName"]]:
                    sawit = True
                #if state not in the life list, we haven't seen it
            
            #For STATEYEAR, look up the current year in the current state
            elif finding == ListType.STATEYEAR:
                if state in lifedict[b["comName"]]:
                    if "2020" in lifedict[b["comName"]][state]:
                        sawit = True
            
            #For YEAR, iterate through each state to see if we've seen the bird in any of them
            elif finding == ListType.YEAR:
                for place in lifedict[b["comName"]]:                #for each place we've seen it
                    if sawit == False: 
                        if "2020" in lifedict[b["comName"]][place]: #if we saw it this year...
                            sawit = True
            
            #For LIFE, just need to mark that we've seen the bird
            else:
                sawit = True
               
            if sawit == False:
                needs.append(b)

        else: #not in lifedict so we should definitely see it
            #Note that we assume we would ALWAYS want to see a bird not in the life list, not matter what
            #type of list we are creating. So, if we want special treatment of finding = ListType.LIFE 
            #then need to add it.
            needs.append(b)
        
    return needs


# turn on logging
#from init import get_module_logger
log = init.get_module_logger(__name__)

#Load the ebird taxonomy
ebirdtaxonomy = ebird.getEbirdTaxonomyDict(init.ebirdtaxonomyfilename)

#Build the mapping of common name to code
#birdcodes = ebird.getBirdName(ebirdtaxonomy)

#Load life list
lifedict = getNALifeDict(init.lifelistfilename, ebirdtaxonomy)
if len(lifedict) == 0:
    log.critical("Major error happened getting life list")
    sys.exit()

#Load and process region data to generate prioritization criteria
regiondata = data.loadAllRegionData(ebirdtaxonomy)

#lat & long for Abita Springs: 30.47, -90.03
state = "US-LA"
lat = 30.47
lng = -90.03
daysback = 7
distKM = 25
showprivateplaces = False
findType = ListType.STATELIFE
if findType == ListType.LIFE:
    findstr = "life list"
elif findType == ListType.STATELIFE:
    findstr = "state life list for the state {}".format(state)
elif findType == ListType.STATEYEAR:
    findstr = "state year list for the state {}".format(state)
else:
    findstr = "year list"

todomsg = "You asked for birds needed for your {}\n".format(findstr)
todomsg += "I looked {} days back, within {}km of GPS coordinates {}, {}. \n".format(daysback, distKM, lat, lng)

sightings = ebird.getSightingsForLocation(lat, lng, daysback, distKM)
if len(sightings) == 0:
    print(todomsg)
    print("Unfortunately, no sightings were reported.")
    sys.exit()

#remove anything that isn't a species from this list
sightings = ebird.filterSpecies(sightings, ebirdtaxonomy)

#Get list of birds we need
needs = getNeedsList(findType, state, sightings, lifedict)
if len(needs) == 0:
    print("You asked for {}, but you've seen it all! No birds needed in this area.".format(findstr))
    sys.exit()

#build a list of all the places where the birds we need have been seen. 
#places is a dict of { "locID" : (birds)}
log.info("Get list of all places where birds we need have been seen")
placespublic = {}
placesprivate = {}
placesdb ={}

for b in needs:
    #Get list of recent sightings for each bird.
    #take this dictionary and merge it with places

    locationlist = ebird.getLocationsForBird(lat, lng, daysback, distKM, b["speciesCode"])
    if len(locationlist) == 0:
        log.critical("Ebird says you need {} but then failed to return any locations".format(b["comName"]))
    else:
        for p in locationlist:
            #p is a place with a locID. if the place is in our dict then add the bird name. 
            #If the place is NOT in our dict then add the place and the bird name
            if p["locationPrivate"] == False:
                if p["locName"] in placespublic:
                    log.debug("Adding {} to public place {}".format(b["comName"], p["locName"]))
                    placespublic[p["locName"]].add(b["comName"])
                else:
                    #place is not in our list, 
                    log.debug("Adding a new place {} for bird {}".format(p["locName"], b["comName"]))
                    placespublic[p["locName"]] = {b["comName"]}
                    placesdb[p["locName"]] = {"lat" : p["lat"], "lng" : p["lng"]}
            #else location IS private
            elif showprivateplaces == True:
                if p["locName"] in placesprivate:
                    log.debug("Adding {} to private place {}".format(b["comName"], p["locName"]))
                    placesprivate[p["locName"]].add(b["comName"])
                else:
                    #place is not in our list, 
                    log.debug("Adding a new private place {} for bird {}".format(p["locName"], b["comName"]))
                    placesprivate[p["locName"]] = {b["comName"]}
                    placesdb[p["locName"]] = {"lat" : p["lat"], "lng" : p["lng"]}
#TODO make all the output into its own module
#TODO probably want to make a giant string and then write the whole thing to the file, that
#way if there is an error with the file, we can still print the results

try:
    f = open("results.txt", "w")
    f.write(todomsg)
    f.write("\n\nPlaces you should go\n")
    f.write("-------------------\n")
    for p in placespublic:
        f.write("{}, {}, {}\n".format(p, placesdb[p]["lat"], placesdb[p]["lng"]))
        for b in placespublic[p]:
            f.write("\t{} ({})\n".format(b,regiondata[state][b]))
    
    if showprivateplaces:
        f.write("\n\Private places we can't go")
        f.write("\n-------------------")
        for p in placesprivate:
            f.write("\n{}".format(p))
            for b in placesprivate[p]:
                f.write("\t{}".format(b))
        else:
            print("None found")
    
    f.close()

except:
    print("TODO Fix the error handling")


#Write results to Google map format
#TODO make error handling match the above
if len(placespublic) > 0:
    f = open("googlemap.csv", "w")
    f.write("Place, Latitude, Longitude, Birds\n")
    for place in placespublic:
        species =""
        i = 0
        for bird in placespublic[place]:
            species += "{} | ".format(bird)
            i += 1
        f.write("{} ({}), {}, {}, {}\n".format(place, i, placesdb[place]["lat"], placesdb[place]["lng"], species))
    f.close()

import json
import csv
import sys
import logging
from enum import Enum
from operator import itemgetter

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


#Ask user which type of list they want to build
def askUserForListType() -> ListType:
    print("What type of list are you building?")
    print("  1) State year list")
    print("  2) State life list")
    print("  3) Year list")
    print("  4) Life list")

    while True:
        try:
            n = input("Choose one: ")
            n = int(n)
            if n >= 1 and n <=4:
                break
        except ValueError:
            print("Not a valid choice, please try again ...")
    
    if n == 1:
        result = ListType.STATEYEAR
    elif n == 2:
        result = ListType.STATELIFE
    elif n == 3:
        result = ListType.YEAR
    else:
        result = ListType.LIFE

    return result


#Generate the message that summarizes what we're doing
def getToDoMsg(findType:ListType, state:str, lat:float, lng:float, daysback:int, distKM:int) -> str:
    result = ""
    if findType == ListType.LIFE:
        findstr = "life list"
    elif findType == ListType.STATELIFE:
        findstr = "state life list for the state {}".format(state)
    elif findType == ListType.STATEYEAR:
        findstr = "state year list for the state {}".format(state)
    else:
        findstr = "year list"

    result = "You asked for birds needed for your {}\n".format(findstr)
    result += "I am looking {} days back, within {}km of GPS coordinates {}, {}. \n".format(daysback, distKM, lat, lng)

    return result


#Generate the list of places we should go, along with the list of birds seen at each
#places is a dict of { "locID" : (birds)}
def getPlacesDict(needs:dict, lat:float, lng:float, daysback:int, distKM:int) -> dict:

    log.info("Get list of all places where birds we need have been seen")
    placesdict = {}
    for b in needs:
        #For each bird we need to see, get list of recent sightings for it.
        locationlist = ebird.getLocationsForBird(lat, lng, daysback, distKM, b["speciesCode"])

        if len(locationlist) > 0:
            for p in locationlist:
                #p is a place with a locID. if the place is in our dict then add the bird name. 
                #If the place is NOT in our dict then add the place and the bird name
            
                if p["locName"] in placesdict:
                    log.debug("Adding {} to public place {}".format(b["comName"], p["locName"]))
                    placesdict[p["locName"]]["seen"].add(b["comName"])

                else:
                    #place is not in our list, 
                    log.debug("Adding a new place {} for bird {}".format(p["locName"], b["comName"]))
                    placesdict[p["locName"]] = {"lat" : p["lat"], "lng" : p["lng"], "private" : p["locationPrivate"], "seen" :{b["comName"]} }
        else:
            log.critical("Ebird says you need {} but then failed to return any locations".format(b["comName"]))
    
    return placesdict


#Generate a string that contains all the birds seen for a particular place
def getPlaceResults(place:str, placedata:dict, regiondata:dict, state:str) -> str:
    result = ""
    result += place + "\n"
    
    birdpriority = {}
    for s in init.birdstatus:
        birdpriority[s] = []

    for b in placedata["seen"]:
        if len(birdpriority[regiondata[state][b]]) > 0:
            birdpriority[regiondata[state][b]].append(b)
        else:
            birdpriority[regiondata[state][b]] = [b]
    
    
    for p in birdpriority:
        for b in birdpriority[p]:
            result += "\t{} ({})\n".format(b,p)
    
    result += "\n\n"

    return result

#make a list of all the keys, sorted in priority order
#v1 = sort by count of birds
def prioritizePlaces(placesdict:dict, regiondata:dict, state:str) -> list:
    
    #make a list of tuples, where first item is the key and the second is the count of birds for that key
    result = []
    for p in placesdict:
        result.append( (p, len(placesdict[p]["seen"])))

    list.sort(result, key=itemgetter(1), reverse=True)

    #strip off the prioritization criteria
    cleanresult = []
    for p in result:
        cleanresult.append(p[0])

    return cleanresult

#Print out all results
def printResults(todomsg:str, placesdict:dict, showprivate:bool, regiondata:dict, state:str) -> bool:
    log.info("Get list of all places where birds we need have been seen")

    print("Saving results to file...")
        
    privateplaceresults = ""
    publicplaceresults = ""

    #The function returns a list of places in priority order. We'll use this as the key for 
    #processing the places dictionary, so that we get the order correct in the output file
    for p in prioritizePlaces(placesdict, regiondata, state):
        if placesdict[p]["private"] == True:
            privateplaceresults += getPlaceResults(p, placesdict[p], regiondata, state)
        else:
            publicplaceresults += getPlaceResults(p, placesdict[p], regiondata, state)
    
    try:
        f = open("results.txt", "w")
        f.write(todomsg)

        if len(publicplaceresults) > 0:
            f.write("\n\nPublic places you can go\n")
            f.write("------------------------\n")
            f.write(publicplaceresults)
        else:
            f.write("\nSorry, no public places found")

        if showprivate:
            if len(privateplaceresults) > 0:
                f.write("\n\nPrivate places of interest")
                f.write("\n--------------------------")
                f.write(privateplaceresults)
            else:
                f.write("\nSorry, no private places found")
    
        f.close()
        print("Successfully saved results file.")

    except:
        print("Error saving results file")

    #Write results to Google map format
    try:
        f = open("googlemap.csv", "w")
        f.write("Place, Latitude, Longitude, Birds\n")
        for p in placesdict:
            if placesdict[p]["private"] == False or (placesdict[p]["private"] == True and showprivate == True):
                species = ""
                i = 0
                for bird in placesdict[p]["seen"]:
                    species += "{} | ".format(bird)
                    i += 1
                if i > 0: #strip off the last |
                    species = species[0 : len(species) - 3]
                f.write("{} ({}), {}, {}, {}\n".format(p, i, placesdict[p]["lat"], placesdict[p]["lng"], species))
        f.close()
        print("Successfully saved Google Map file.")
    except:
        print("Could not save Google Map file.")



#
#
#  Main program starts here
#
#

# turn on logging
log = init.get_module_logger(__name__)

#Load the ebird taxonomy
ebirdtaxonomy = ebird.getEbirdTaxonomyDict(init.ebirdtaxonomyfilename)

#Load life list
lifedict = getNALifeDict(init.lifelistfilename, ebirdtaxonomy)
if len(lifedict) == 0:
    log.critical("Major error happened getting life list")
    sys.exit(0)

#Load and process region data to generate prioritization criteria
regiondata = data.loadAllRegionData(ebirdtaxonomy)

#lat & long for Abita Springs: 30.47, -90.03
state = "US-LA"
lat = 30.47
lng = -90.03
daysback = 7
distKM = 25
showprivateplaces = False
findType = askUserForListType()

todomsg = getToDoMsg(findType, state, lat, lng, daysback, distKM)
print(todomsg)

sightings = ebird.getSightingsForLocation(lat, lng, daysback, distKM)
if len(sightings) == 0:
    print("Unfortunately, no sightings were reported by eBird for your criteria.")
    sys.exit(0)

#remove anything that isn't a species from this list
sightings = ebird.filterSpecies(sightings, ebirdtaxonomy)

#Get list of birds we need
needs = getNeedsList(findType, state, sightings, lifedict)
if len(needs) == 0:
    print("You've seen it all! No birds needed in this area that meet your criteria.")
    sys.exit(0)

#get all the places where the birds we need have been seen. 
placesdict = getPlacesDict(needs, lat, lng, daysback, distKM)

#generate the files with the results in them
printResults(todomsg, placesdict, showprivateplaces, regiondata, state)

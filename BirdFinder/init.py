#logging
import logging

def get_module_logger(mod_name):
  logger = logging.getLogger(mod_name)
  handler = logging.StreamHandler()
  formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  #possible logging values are: DEBUG (verbose), INFO (medium), CRITICAL (minimal)
  logger.setLevel(logging.CRITICAL)
  return logger


#Basic data
lifelistfilename = "MyEBirdData.csv"
ebirdtaxonomyfilename = "ebird taxonomy.csv"

from enum import Enum
class Category(Enum):
    DOMESTIC = "domestic"
    FORM = "form"
    HYBRID = "hybrid"
    INTERGRADE = "intergrade"
    ISSF = "issf"
    SLASH = "slash"
    SPECIES = "species"
    SPUH = "spuh"

class EBirdDictColumns(Enum):
    SCIENTIFIC_NAME = "SCIENTIFIC_NAME"
    COMMON_NAME = "COMMON_NAME"
    SPECIES_CODE = "SPECIES_CODE"
    CATEGORY = "CATEGORY"
    TAXON_ORDER = "TAXON_ORDER"
    COM_NAME_CODES = "COM_NAME_CODES"
    SCI_NAME_CODES = "SCI_NAME_CODES"
    BANDING_CODES = "BANDING_CODES"
    ORDER = "ORDER"
    FAMILY_COM_NAME = "FAMILY_COM_NAME"
    FAMILY_SCI_NAME = "FAMILY_SCI_NAME"
    REPORT_AS = "REPORT_AS"
    EXTINCT = "EXTINCT"
    EXTINCT_YEAR = "EXTINCT_YEAR"


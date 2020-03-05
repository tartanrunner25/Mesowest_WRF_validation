import os.path as osp
import re, glob, sys, os


#This script download station data based on settings that we prescribe. Depending on the data
#we want will dictate what we submit to the mesowest API. For example, are we grabbing a single 
#station, or grabbing multiple stations?
 
#First, grab our inputs. Start by asking for time period, variables we want, and the name 
#of our output file, our MesoWest/Synoptic Labs API, ect.....

api_suffix = "http://api.mesowest.net/v2/stations/timeseries?"

start_time = input("Enter start time as YYYYMMDDHHMM: ")
end_time = input("Enter end time as YYYYMMDDHHMM: ")

print("")
print("")
print("What variables do we want?")
print("")
print("Variable names must be inputted as listed at:")
print("https://developers.synopticdata.com/about/station-variables/")
print("")
print("If multiple variables are being inputted, seperate variable names with a comma!")
print("For exammple: wind_speed,wind_direction,air_temp")
vars_want = input("What variable(s) do we want? ")

print("")
print("")
print("All station(s) data that meets our criteria will be saved as a json object...")
out_name = input("Name of our output file (excluding out file extension)?  ")
out_name = out_name+'.json'

#print("")
#print("")
#print("Do we want to manually select your station(s) or automatically grab all stations that fall within a radius?")
#api_key = input("What is our Synoptic labs API key?': ")
#I just hard coded the api token since this won't change for me....
api_key = '&token='+'YOUR KEY HERE'

print("")
print("")
print("Do we want to manually select your station(s) or automatically grab all stations that fall within a radius?")
radiusTF = input("Select either 'Auto' or 'Manual': ")


#Checks to see whether we've opted to go with the radius selection or just want specific 
#station(s), which are manually selected.
if radiusTF == 'Auto':
    print("")
    print("")
    print("You have selected the 'radius' option")
    print("")
    lat = input("Please enter a latitude: ")
    lon = input("Please enter a longitude: ")
    radius = input("Please enter a radius (in miles): ")
    network = input("Enter preferred network(s): ")

    api_submit = "'"+api_suffix+"radius="+lat+","+lon+","+radius+"&network="+network+"&start="+start_time+"&end="+end_time+"&obtimezone=utc"+api_key+"&timeformat=%Y%m%d%20%H%M%S&vars="+vars_want+"'"

else: 
    print("")
    print("")
    print("You have selected to manually select your stations...")
    stat_name = input("Enter your station ID: ")

    api_submit = "'"+api_suffix+"stid="+stat_name+"&start="+start_time+"&end="+end_time+"&obtimezone=utc"+api_key+"&timeformat=%Y%m%d%20%H%M%S&vars="+vars_want+"'"

#Submit our API request using wget -O, where -O allows us to specify an output name 
print("Submitting API request for: "+api_submit)
os.system("wget -O "+out_name+" "+api_submit)


#End script



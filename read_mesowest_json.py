import json
import os.path as osp
import re, glob, sys, os
import numpy as np
import pandas as pd
from datetime import datetime
from datetime import timezone
from handy_wrf_funcs import init_wrf_time, grab_site_var, interp_near
from wrf import (to_np, getvar)
from netCDF4 import Dataset

#This scripts reads in JSON data which we grabbed using the mesowest API, 
#and then takes the lat lon information for each station to determine location
#on WRF grid. This script then pulls WRF data for each station that we pass to 
#it and plots the data up.
#Tips for working with JSON objects on Brian Baylock's blog:
#
#https://kbkb-wx-python.blogspot.com/2015/06/python-and-mesowest-api.html

#Input files location?
my_json = 'mesowest_dat_092018_SLV.json'
wrf_path = './WRF_files/'

#Preferred network for analysis that corresponds to the identification listed
#here: https://developers.synopticdata.com/about/station-providers/
pref_network = [1,2,4,9,153]

#Read in json formatted mesowest data
with open(my_json) as json_file:
    data = json.load(json_file)

#Determine number of dictiomary entries as we'll want to pre-allocate any areas with this 
#information, while also knowing which index to loop over...
stat_num = len(data['STATION'])

#What variables do we except in this code? We have to match our observed variable
#names to WRF variable names, which is done manually. Thus we only have a list of 
#variables can accept, and all others will be skipped later on. If not using 
#WRF-SFIRE-CHEM or WRF-CHEM... drop 'PM_25_concentration'.
var_accept = ['air_temp','wind_speed','wind_direction','relative_humidity','PM_25_concentration']
wrf_accept = ['T2','uvmet10_wspd','uvmet10_wdir','rh2','PM2_5_DRY']
df_header = list(['times','statID','netID','lat','lon'])+var_accept+wrf_accept

#What WRF files are we working with? Read in lat lon information, so we know what
#stations fall outside of our WRF boundaries...
wrf_files = sorted(glob.glob(osp.join(wrf_path, 'wrfout_d02*')))
ncfile = Dataset(wrf_files[0])
wlat = getvar(ncfile, "XLAT")
wlon = getvar(ncfile, "XLONG")
maxlat = np.amax(wlat)
minlat = np.amin(wlat)
maxlon = np.amax(wlon)
minlon = np.amin(wlon)
ncfile.close()

#Get WRF times, also convert them to seconds since epoch time. 
wrf_times = init_wrf_time(wrf_files)
wrf_secs = (wrf_times.astype('O')/1e9).astype(float)

#Initialize data frame counter to determine when to append
df_boolean = 0

#Loop through each station (s)
for s in range(0,stat_num):
    print("Working on station: ("+str(s)+") "+data['STATION'][s]['NAME'])

    #Determine station variables we are working with, the station short name,
    #and the station lat lons, which we will be used to find the corresponding 
    #WRF i j point. 
    stat_vars = list(data["STATION"][s]["SENSOR_VARIABLES"])
    short_name = data['STATION'][s]['STID']
    stat_lon = float(data['STATION'][s]['LONGITUDE'])
    stat_lat = float(data['STATION'][s]['LATITUDE'])
    networkID = float(data["STATION"][s]["MNET_ID"])

    #Check statements to determine whether our station's lat lon fall within 
    #our WRF domain? If not, we should skip our station via a continue statement.
    if(stat_lon  < minlon or stat_lon > maxlon or stat_lat < minlat or stat_lat > maxlat):
        print("Station falls outside of our WRF domain")
        continue

    if networkID not in pref_network:
        print("Station not in our preferred network list")
        continue
    
    #Grab observation time and convert to a datetime object. Time should be set 
    #as UTC. Also convert to numeric (seconds since epoch time).
    dates = data["STATION"][s]["OBSERVATIONS"]["date_time"]
    dates_list = [datetime.strptime(date, '%Y%m%d %H%M%S') for date in dates]
    obs_dates = [date_list.replace(tzinfo=timezone.utc).timestamp() for date_list in dates_list]

    #Lets create a blank data frame, which will filled in by our variables from
    #WRF and the station we are working on. This will have dimensions of time length 
    #and variable number t x n. WRF output will not be on same time-interval, so 
    #we'll need to do some interpolation later on based on WRF times. Variables than
    #don't exist will jsut be left as NaN
    index = np.arange(0,len(obs_dates),1)
    tmp_df = pd.DataFrame(index=index,columns=df_header)
    tmp_df.loc[:,"times"] =  dates_list
    tmp_df.loc[:,"statID"] =  [short_name] * len(obs_dates)
    tmp_df.loc[:,"netID"] =  [int(networkID)] * len(obs_dates)
    tmp_df.loc[:,"lat"] =  [stat_lat] * len(obs_dates)
    tmp_df.loc[:,"lon"] =  [stat_lon] * len(obs_dates)

    #Loop through each variable that we have 
    for v in range(0,len(stat_vars)):

        #Use dictionary to determine variable name we are working with, and use that
        #definition to pull our variable. If our variable name does not equal one of our 
        #standard variables defined via var_accept, do not try to find this within WRF.
        var_name = list(data["STATION"][s]["SENSOR_VARIABLES"][stat_vars[v]])[0]

        if stat_vars[v] not in (var_accept): 
            continue

        #np.array will convert any "none" values to np.nan, which is convienient. This gets 
        #store in our obs array. 
        tmp_df.loc[:,stat_vars[v]] = np.array(data["STATION"][s]["OBSERVATIONS"][var_name],dtype=float)

        #Next, lets grab our WRF data. First, we need to match our station variable
        #name with the corresponding WRF variable name. If there is not a match, the 
        #continue statement above should catch this.
        if stat_vars[v] == "air_temp":wrf_var = "T2"
        if stat_vars[v] == "relative_humidity":wrf_var = "rh2"
        if stat_vars[v] == "PM_25_concentration":wrf_var = "PM2_5_DRY"
        if stat_vars[v] == "wind_speed":wrf_var = "uvmet10_wspd"
        if stat_vars[v] == "wind_direction":wrf_var = "uvmet10_wdir"

        tmp_var = grab_site_var(wrf_files,wrf_var,stat_lat,stat_lon)

        #Do unit conversions depending on variable we are working with. The linearly interpolate 
        #our variable. For wind direction, which is a vector, we would need to decompose the u and 
        #v-wind components, which requires reading in a different variable, and adding some complexities
        #to our code. Lets jut take the nearest wind value as an assumption, since our WRF output is 
        #pretty frequent, then save to our WRF array.
        if stat_vars[v] == "air_temp": tmp_var = tmp_var - 273.15
        if stat_vars[v] == "uvmet10_wdir":
            tmp_df.loc[:,wrf_var] = interp_near(np.array(obs_dates),wrf_secs,tmp_var,outside=np.nan)
        else:
            tmp_df.loc[:,wrf_var] = np.interp(obs_dates,wrf_secs,tmp_var,right=np.nan,left=np.nan)
    
    #Save data frame to our output data frame. If this is our first time doing this, just set our
    #temporary data frame to 'df_alldat', else just append the pandas data frame.
    if df_boolean == 0:
        df_alldat = tmp_df 
    else:
        df_alldat = df_alldat.append(tmp_df,ignore_index=True)

    df_boolean = 1


#Save our output as a pkl object, which maintains the data frame format if exhanging this with 
#other python code  
#pd.set_option('display.max_rows', None)
#print(df_alldat)
df_alldat.to_pickle("./model_matched_obs.pkl")

#End script
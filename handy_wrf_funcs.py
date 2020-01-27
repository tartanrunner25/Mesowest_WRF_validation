from netCDF4 import Dataset
from wrf import (to_np, getvar, smooth2d, get_cartopy,ll_to_xy,latlon_coords)
import numpy as np
from datetime import datetime
import re, glob, sys, os
import matplotlib
import matplotlib.cm as cm
from matplotlib.cm import get_cmap


#This script contains a number of handy and re-usable functions for manipulating WRF data
#on the fly. These routines also include functions related to WRF-SFIRE and WRFx. Current
#routines include:
#   (1) color mapper        -converts scalar quantity to mapped color scale RGBA value
#   (2) grab_site_var       -grabs sfc station data for given lat/lon pairs
#   (3) init_wrf_time       -initializes time length of WRF simulation
#   (4) interp_near         -interpolate 1D field to specified time point using nearest neighbor
#   (5) read_fire_kml       -reads in kml fire perimeter data


def color_mapper(scalar_val,minv,maxv,color_table):

    #This function creates a mapper that translates a scalar quantity at a station to
    #RGBA color scale, for a given color map.
    #input param: scalar_val   - scalar quantify we wish to convert to RGBA
    #input param: minv         - minimum threshold for scalar quanitfy
    #input param: maxv         - maximum threshold for scalar quanitfy
    #input param: color_table  - what color table do we wish to use?
    #returns: col_var          - converted scalar quantity as RGBA

    norm = matplotlib.colors.Normalize(vmin=minv, vmax=maxv, clip=True)
    mapper = cm.ScalarMappable(norm=norm, cmap=get_cmap(color_table))
    col_var = mapper.to_rgba(scalar_val)

    return(col_var)


def grab_site_var(wrf_files,wrf_var,lats,lons):

    #This function returns values for the WRF variable supplied 
    #here, at the designated lat lon, for each time within the 
    #specified WRF files. This only for surface variables on a 
    #2-D/3-D grid (i,j or i,j,t)
    #input param: wrf_files - list of wrf file(s) to read in
    #input param: var_name  - what WRF variable do we want to grab?
    #input param: lat       - latitude(s) of our site (decimal degrees)
    #input param: lat       - latitude(s) of our site (decimal degrees)
    #returns: out_var       - return a vector for the variable name given
    #                       - at the respective lat lon location 


    #Determine whether we have a single file 'str' or a list of files 'list'
    if isinstance(wrf_files,str):
        
        ncfile = Dataset(wrf_files)
        my_var = getvar(ncfile,wrf_var,timeidx=None,squeeze=False)
        var_shape = my_var.shape 

        i_j = ll_to_xy(ncfile,lats,lons)

        #Differentiate between surface variables with a single vertical level 
        # and surface variables that have a vertical dimension.
        if len(var_shape) == 3:
            out_var = my_var[:,i_j[1,],i_j[0,]]
        if len(var_shape) == 4:
            out_var = my_var[:,0,i_j[1,],i_j[0,]]
        
        ncfile.close()

    else:

        #Else we must have multiple files, so loop through each one....
        for f in range(0,len(wrf_files)):
 
            ncfile = Dataset(wrf_files[f])
            my_var = getvar(ncfile,wrf_var,timeidx=None,squeeze=False)
            var_shape = my_var.shape 

            i_j = ll_to_xy(ncfile,lats,lons)

            #Differentiate between surface variables with a single vertical level 
            # and surface variables that have a vertical dimension.
            if len(var_shape) == 3:
                sub_var = my_var[:,i_j[1,],i_j[0,]]
            if len(var_shape) == 4:
                sub_var = my_var[:,0,i_j[1,],i_j[0,]]

            #Store our variable or append it
            if f == 0:
                out_var = sub_var
            else:
                out_var = np.concatenate((out_var,sub_var), axis=0)
            
            ncfile.close()

    return(out_var)


def init_wrf_time(wrf_files):

    #Reads in all WRF files that are supplied, and returns the size
    #of the WRF time array we are working with.

    #input param: wrf_files - list of wrf file(s) to read in 
    #returns: wrf_times - vector of all wrf times


    #Determine whether we have a single file 'str' or a list of files 'list'
    if isinstance(wrf_files,str):
        ncfile = Dataset(wrf_files)
        wrf_times = getvar(ncfile, "times",timeidx=None,squeeze=False,meta=False)
    else:

        #We must have multiple files, so loop through each one....
        for f in range(0,len(wrf_files)):

            # Open the NetCDF file and read in time variable
            ncfile = Dataset(wrf_files[f])
            times = getvar(ncfile, "times",timeidx=None,squeeze=False,meta=False)
            ncfile.close()

            #Store our time or append it
            if f == 0:
                wrf_times = times 
            else:
                wrf_times = np.append(wrf_times,times)

    return wrf_times


def interp_near(xi, x, y, outside=None):

    #Interpolate our 1D data using the nearest neighbor approach. 

    #input param: xi      - points we want to interpolate to (type: np.array)
    #input param: x       - points we want to interpolate from (type: np.array)
    #input param: y       - scalar quantity that we want to interpolate with
    #input param: outside - a element that determines how to set values outside 
    #                       of the range provided. Else if 'None', just extrapolate

    idx = np.abs(x - xi[:,None])
    y = y[idx.argmin(axis=1)]

    #If outside is set to something other than none, we do not want to extrapolate
    #to areas outside of the range provided.
    if outside is not None:
        y[(xi < x[1]) | (xi > x[len(x)-1])] = outside

    return y
    


def read_fire_kml(kml_path,kml_file):

    #Reads in fire perimeter file in kml format (from GeoMac), and 
    #finds the lat/lon coordinates for each fire perimeter polygon.
    #Lat lon coordates are then returned as an array. Written by
    #Angel Farguell, modified by DVM 10/16/2019

    #input param: kml_path - path for our kml file 
    #input param: kml_file - name of our kml file 

    #return: kml_latlon - lat lon coordinates for our perimeter 

    f = open(kml_path+kml_file,"r")
    f_str = ''.join(f.readlines())
    f.close()

    name = re.findall(r'<name>(.*?)</name>',f_str,re.DOTALL)[0]
    date = re.match(r'.*([0-9]{2}-[0-9]{2}-[0-9]{4} [0-9]{4})',name).groups()[0]

    # Get the coordinates of all the perimeters
    # regex of the polygons (or perimeters)
    polygons = re.findall(r'<Polygon>(.*?)</Polygon>',f_str,re.DOTALL)

    # for each polygon, regex of the coordinates
    buckets = [re.split(r'\n\s+',re.findall(r'<coordinates>(.*?)</coordinates>',p,re.DOTALL)[0])[1:] for p in polygons]

    # array of arrays with each polygon coordinates
    kml_latlon = [[np.array(re.split(',',b)[0:2]).astype(float) for b in bucket] for bucket in buckets]

    return(kml_latlon)








    


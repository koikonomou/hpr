#!/usr/bin/env python
__author__="athanasia sapountzi"

import roslib, warnings, rospy, math, pickle, scipy.stats
from gridfit import gridfit
import numpy as np
import scipy.spatial.distance as dist
import scipy.io as sio
import scipy.special
import matplotlib.pyplot as plt
import mytools as mt #DBSCAN function and perquisites are stored here
import sys
import os.path
import time
from os import listdir
from os.path import isfile, join, splitext
from myhog import hog
from sensor_msgs.msg import LaserScan
from scipy.stats.mstats import zscore
from scipy import interpolate
from sklearn.decomposition import PCA

ccnames =['gray', 'black', 'violet', 'blue', 'cyan', 'rosy', 'orange', 'red', 'green', 'brown', 'yellow', 'gold']
cc  =  ['#808080',  'k',  '#990099', '#0000FF', 'c','#FF9999','#FF6600','r','g','#8B4513','y','#FFD700']
wall_flag=0
fr_index=1
z=0
dt = 25;#period in ms (dt between scans)
speed = 5;#human walking speed in km/h
z_scale= float(speed*dt) / float(3600)
w_index=1
limit=3
scan_active = True
classification_array = []
scan_received = 0
plt.ion()
class_path = ''
pca_path = ''
pca_obj = PCA()
annotation_file = ''
first_time = True
first_time_ranges = True
sub_topic = 'scan'
metrics = 0
total_cluster_time = 0
hogs_temp=[]

annotated_humans = 0
annotated_obstacles = 0

#temp2 = np.zeros((1, 36))

def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False
        
def RepresentsFloat(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

'''
def Calculate_Metrics(annotated_data):
    global classification_array
    pos = 1
    true_pos = 0.0
    true_neg = 0.0
    false_pos = 0.0
    false_neg = 0.0
    neg = 0
    #print len(annotated_data)
    classification_array = np.array(classification_array)
    #print len(classification_array)
    for i in range(len(classification_array)):
        if annotated_data[i]==1:
            if classification_array[i]==1:
                true_pos += 1.0
            else:
                false_neg += 1.0
        else:
            if classification_array[i]==1:
                false_pos += 1.0
            else:
                true_neg += 1.0
    precision = true_pos/(true_pos + false_pos)
    recall = true_pos/(true_pos + false_neg)
    accuracy = (true_pos + true_neg)/(true_pos + false_pos + true_neg + false_neg)
    print "Precision : {0}".format(precision)
    print "Recall : {0}".format(recall)
    print "Accuracy : {0}".format(accuracy)
    input ("Press any key to exit")
    return
''' 


def laser_listener():
    
    global class_path, pca_path, sub_topic, timewindow, range_limit
    global annotations
    global gaussian, pca_obj
    global timewindow, range_limit, annotated_data, classification_array
    global all_clusters, all_hogs, all_gridfit, all_orthogonal,all_annotations
    
    all_clusters=[]
    all_hogs=[]
    all_gridfit=[]
    all_orthogonal=[]
    all_annotations=[]

    if not len(sys.argv) == 7:
        print "###################################"
        print "For non interactive input run as follows : "
        print "python hpr.py <classifier_object_path> <pca_objec_path> <laserscan_topic> <timewindow_in_frames> <maximum_scan_range> <0_or_1_for_metrics>"
        print "###################################"
        exit()
    else:
        class_path = str(sys.argv[1])
        pca_path = str(sys.argv[2])
        if not os.path.isfile(class_path):
            while True :
                try:
                    class_path=raw_input('Enter classifier object file path: ')
                    if os.path.isfile(class_path):
                        break
                    else:
                        print 'File does not exist! Try again!'
                except SyntaxError:
                    print 'Try again'
        print "Classifier File : {0}".format(class_path)
        
        if not os.path.isfile(pca_path):
            while True :
                try:
                    pca_path=raw_input('Enter pca object file path: ')
                    if os.path.isfile(pca_path):
                        break
                    else:
                        print 'File does not exist! Try again!'
                except SyntaxError:
                    print 'Try again'
        print "File : {0}".format(pca_path)

        rospy.init_node('laser_listener', anonymous=True)
        #ADDITIONS command line inputs klp
        scan_topic = str(sys.argv[3])
        timewindow = int(sys.argv[4])
        while not RepresentsInt(timewindow):
            timewindow=input('Set timewindow in frames: ')
            if RepresentsInt(timewindow):
                break
            else:
                print 'Try again'
        range_limit = float(sys.argv[5])
        while not (RepresentsInt(range_limit) or RepresentsFloat(range_limit)):
            range_limit=input('Set maximum scan range in m: ')
            if RepresentsInt(range_limit):
                break
            else:
                print 'Try again'

        metrics = int(sys.argv[6])
        while not (RepresentsInt(metrics) and metrics != '1' and metrics != '0'):
            metrics=input('Set if you want performance metrics or not: ')
            if RepresentsInt(metrics):
                break
            else:
                print 'Try again'
   
    print "Classifier object path : ", class_path 
    print "PCA object path : ", pca_path
    print "Scan Topic : ", sub_topic
    print "Timewindow (frames) : ",timewindow
    print "Maximum scan range (meters)", range_limit
    print "Waiting for laser scans ..."
    #ADDITIONS command line inputs klp
    
    rospy.Subscriber(sub_topic,LaserScan,online_test)
    scan_received=rospy.Time.now().to_sec()
    gaussian, pca_obj = loadfiles()
    while not rospy.is_shutdown():  
        rospy.spin()
    #we come here when Ctrl+C is pressed, so we can save!
    if metrics == 1:
        b={}
        b['timewindow']=timewindow
        b['range_limit']=range_limit
        b['angle_increment']=angle_increment
        #b['scan_time']=scan_time
        b['angle_min']=angle_min
        b['angle_max']=angle_max
        b['intensities']=intensities
        b['wall']=wall
        print b['wall']
        b['annotations']=annotations
        b['ranges']=ranges_
        try:
            os.remove('classification_results.mat')
        except OSError:
            pass
        sio.savemat('classification_results',b);

    print 'duration in milliseconds = {0}'.format(total_cluster_time)
    #save_data(all_clusters, all_orthogonal, all_gridfit, all_hogs, all_annotations)
    print "D O N E !"
    #Calculate_Metrics(annotated_data)
    #sys.exit()


def online_test(laser_data):
    global wall_flag, wall, fr_index, intens, w_index, phi, sampling, limit #prosthesa to limit edw giati den to epairne global
    global phi, mybuffer, z, zscale, gaussian,timewindow , wall_cart,ax, ax3 ,fig1,fig4, kat
    global pca_obj, pca_plot
    global ranges_, intensities, angle_increment, scan_time, angle_min, angle_max, first_time_ranges, total_cluster_time
    global mybuffer2, num_c
    global all_clusters, all_hogs, all_gridfit, all_orthogonal,all_annotations



    millis_start = int(round(time.time() * 1000))
    if wall_flag == 0:
        #print "-------------- 1"
        if w_index == 1:
            #print "-------------- 2"
            sampling = np.arange(0,len(np.array(laser_data.ranges)),2)#apply sampling e.g every 2 steps

            #wall data now contains the scan ranges
            wall = np.array(laser_data.ranges)
            
            mybuffer = wall
            #get indexes of scans >= range_limit
            filter=np.where(wall >= range_limit)
            #set those scans to maximum range
            wall[filter] = range_limit
            w_index=w_index+1
            
        if w_index<limit: #loop until you have enough scans to set walls
            #print "-------------- 3"
            wall = np.array(laser_data.ranges)
            filter = np.where(wall >= range_limit)
            wall[filter] = range_limit
            mybuffer = np.vstack((mybuffer,wall ))  #  add to buffer with size=(wall_index x 360)
            w_index = w_index+1
        if w_index==limit:
            #print "-------------- 4"
            mybuffer = np.vstack((mybuffer,wall ))
            phi = np.arange(laser_data.angle_min,laser_data.angle_max,laser_data.angle_increment)[sampling]
            wall = (np.min(mybuffer, axis=0)[sampling])-0.1 #select min of measurements
            wall_cart = np.array(pol2cart(wall,phi,0) ) #convert to Cartesian
            wall_flag = 1
            ax,ax3=initialize_plots(wall_cart)

            angle_increment=laser_data.angle_increment
            scan_time=laser_data.scan_time
            angle_min=laser_data.angle_min
            angle_max=laser_data.angle_max
            intensities=laser_data.intensities
	    angle_prev=angle_min
            print 'walls set...'
        
    else:
        #walls are set, process scans
        #print "-------------- 5"
        ranges = np.array(laser_data.ranges)[sampling]
        filter = np.where(ranges < wall) # filter out walls
        ranges = ranges[filter]
        theta = phi[filter]


        if metrics == 1:
            if first_time_ranges:
                ranges_= np.array(laser_data.ranges)[sampling]
                first_time_ranges = False
            else:
                ranges_ = np.vstack((ranges_, np.array(laser_data.ranges)[sampling]))

        if (len(ranges)>3): #each scan should consist of at least 3 points to be valid
            #print "-------------- 6"
            C = np.array(pol2cart(ranges,theta,z) ) #convert to Cartesian


            if (fr_index ==1 ):
                mybuffer = C #mybuffer is the cartesian coord of the first scan
		mybuffer2 = [C]
		num_c = np.array(len(C))
	
            else :
                mybuffer = np.concatenate((mybuffer,C), axis=0 )  #  add the next incoming scans to mybuffer until you have <timewindow>scans
		mybuffer2.append((mybuffer2,[C]))
		num_c=np.vstack((num_c,len(C)))

            if (fr_index == timewindow ):
                mybuffer=mybuffer[np.where( mybuffer[:,0] > 0.2),:][0] #mishits safety margin
                mybuffer=mybuffer[np.where( mybuffer[:,0] < 5),:][0]#ignore distant points


                if len(mybuffer>3): #at least 3 points are needed to form a cluster
		    clustering_procedure(mybuffer, num_c)
 
                fr_index=0
                z=- z_scale
            z = z + z_scale
            fr_index=fr_index+1

    millis_end = int(round(time.time() * 1000))
    total_cluster_time = total_cluster_time + millis_end - millis_start



def pol2cart(r,theta,zed):

    #convert cylindical coordinates to cartesian ones
    x=np.multiply(r,np.cos(theta))
    y=np.multiply(r,np.sin(theta))
    z=np.ones(r.size)*zed
    C=np.array([x,y,z]).T
    return C


def loadfiles():
    
    global class_path
    global all_annotations
    global pca_path
    

    classifier = pickle.load( open( class_path, "rb" ) )
    pca_obj = pickle.load(open ( pca_path, "rb"))
    #all_annotations = pickle.load(open("cluster_labels/video5annotations.p","rb"))
    
    return classifier, pca_obj


def initialize_plots(wall_cart):
    global fig1,fig4

    #2D projection of the cluster
    '''
    temp=plt.figure()
    plot2d = temp.add_subplot(111)
    plot2d.set_xlabel('Vertical distance')
    plot2d.set_ylabel('Robot is here')
    plot2d.plot(wall_cart[:,0],wall_cart[:,1])
    '''


    #3D clusters
    fig1=plt.figure()
    plot3d= fig1.gca(projection='3d')
    plot3d.set_xlabel('X - Distance')
    plot3d.set_ylabel('Y - Robot')
    plot3d.set_zlabel('Z - time')

    #translate and rotate the 3D cluster
    fig4=plt.figure()
    plot_align= fig4.gca(projection='3d')
    plot_align.set_xlabel('X - Distance')
    plot_align.set_ylabel('Y - Robot')
    plot_align.set_zlabel('Z - time')


    plt.show()
    return plot3d,plot_align

def save_data(point_clouds, alignment, gridfit, hogs, annotations) :

    b={}
    b['point_clouds']=point_clouds
    b['alignment']=alignment
    b['gridfit']=gridfit
    b['hogs']=hogs
    b['annotations']=annotations

    sio.savemat('data',b);
    

def translate_cluster(x, y, z) :

    xmean=np.mean(x)
    ymean=np.mean(y)
    zmean=np.mean(z)

    new_x=[]
    new_y=[]
    new_z=[]

    for i in range(0, len(x)):
	new_x.append(x[i]-xmean)
	new_y.append(y[i]-ymean)
	new_z.append(z[i]-zmean)


    return [new_x,new_y,new_z]



def clustering_procedure(clear_data, num_c):

    global cc, ccnames, fig1, z, z_scale, fig4
    global all_clusters,all_hogs,all_gridfit,all_orthogonal
    
    #warnings.filterwarnings("ignore", category=DeprecationWarning)
    hogs=[]
    colors=[]
    align_cl=[]	#contains the aligned data clouds of each cluster
    vcl=[] #Valid Cluster Labels 
    valid_flag=0 #this flag is only set if we have at leat one valid cluster

    Eps, cluster_labels= mt.dbscan(clear_data,3) # DB SCAN

    max_label=int(np.amax(cluster_labels))


    #[xi,yi,zi]: the array of data points of the specific frame
    [xi,yi,zi] = [clear_data[:,0] , clear_data[:,1] , clear_data[:,2]]

    fig1.clear()
    fig4.clear()
    

    #for every created cluster get its data points
    for k in range(1,max_label+1) :
        filter=np.where(cluster_labels==k)
        if len(filter[0])>40 :
	    print 'cluster ',k

            valid_flag=1

	    #points of every cluster at each timewindow-frame
	    [xk,yk,zk]=[xi[filter],yi[filter],zi[filter]]
	    trans_matrix =[[xk,yk,zk]]
	    all_clusters.append([xk,yk,zk])


	    #we get U by appying svd to the covariance matrix. U represents the rotation matrix of each cluster based on the variance of each dimention.
	    U,s,V=np.linalg.svd(np.cov([xk,yk,zk]), full_matrices=False)

	    #translate each cluster to the begining of the axis and then do the rotation
	    [xnew,ynew,znew]=translate_cluster(xk,yk,zk)

	    #(traslation matrix) x (rotation matrix) = alignemt of cluster
	    alignment_result=[[sum(a*b for a,b in zip(X_row,Y_col)) for Y_col in zip(*[xnew,ynew,znew])] for X_row in U]
	    
	    align_cl.append(alignment_result)
	    all_orthogonal.append(alignment_result)

	
	    vcl.append(k)
            colors.append(ccnames[k%12])
            grid=gridfit(alignment_result[0], alignment_result[1], alignment_result[2], 16, 16) #extract surface - y,z,x alignment_result[1]
	    all_gridfit.append(grid)

            grid=grid-np.amin(grid)

	    features=hog(grid)
	    all_hogs.append(features)
            hogs.append(features)  #extract hog features


    
    fig1.show()
    fig4.show()


    update_plots(valid_flag,hogs,xi,yi,zi,cluster_labels,vcl, align_cl)



#TO DO
def speed(num_c,xnea,ynew,znew):

    global pol_degree

    pp=0
    prev=0
    count=0
    std=[]
	    
    for p in range(0,len(num_c)) :
		
	if count<=pol_degree:
	    pp=pp+num_c[p]
	    count=count+1
	    continue

	[xp,yp,zp]=[xnew[prev:prev+pp-1], ynew[prev:prev+pp-1], znew[prev:prev+pp-1]]
	if(len(xp)==0):
	    break

	std.append(np.var([xp,yp,zp]))
	
	prev=pp+prev
	pp=0
	count=0

	print 'std={} '.format(std)


def update_plots(flag,hogs,xi,yi,zi,cluster_labels,vcl, align_cl):
    
    global fig1, ax, ax3, wall_cart, gaussian, classification_array, pca_obj, hogs_temp, align_plot, fig4
    global annotations, first_time, all_annotations,annotated_humans,annotated_obstacles

    temp = []
    store_results = []
    centerx = []
    centery = []
    centerz = []

    #zscore the entire hogs table, not single cluster hogs
    if flag==1:
        #kat.clear()
        #kat.plot(wall_cart[:,0],wall_cart[:,1])

        if np.array(hogs).shape==(1,36):
            temp = zscore(np.array(hogs)[0])

        else:
            for i in range(0,len(hogs)):
                temp.append(zscore(np.array(hogs[i])))
        
        
	temp_pca = pca_obj.transform(temp)
        results = gaussian.predict(temp_pca)
        print results

        cnt=0
	col_list=[]

        for k in vcl:
	    fig1.clear()
            filter=np.where(cluster_labels==k)
            
            [x,y,zed] = [xi[filter] , yi[filter] , zi[filter]]

	    [xc,yc,zc] = [align_cl[cnt][0], align_cl[cnt][1], align_cl[cnt][2]]


	    if len(xc)==0:
		print 'out of data'
		continue

	    #print 'xc = {} align_cl[cnt][0] ={}'.format(xc,align_cl[cnt][0])

            if results[cnt]==1:
                #classification_array.append(1)
                #kat.scatter(x,y,s=20, c='r')
                ax.scatter(x,y, zed, 'z', 30, cc[k%12]) #human
		ax.scatter(xc,yc, zc, 'z', 30, cc[k%12]) #human
                fig1.add_axes(ax)

		#ax3.scatter(xc,yc, zc, 'z', 30, cc[k%12]) #human
                #fig4.add_axes(ax3)
            else:
                #classification_array.append(0)
                #kat.scatter(x,y,s=20, c='b')
                ax.scatter(x,y, zed, 'z', 30, cc[k%12]) #object
		ax.scatter(xc,yc, zc, 'z', 30, cc[k%12]) #human
                fig1.add_axes(ax)

		#ax3.scatter(xc,yc, zc, 'z', 30, cc[k%12]) #human
                #fig4.add_axes(ax3)
	    
	    cnt=cnt+1
	    fig1.show()

	    '''
	    ha = raw_input()
            if (int(ha)==1 or int(ha)==0):
                ha = int(ha)
                if ha == 1:
                    annotated_humans = annotated_humans + 1
                else :
                    annotated_obstacles = annotated_obstacles + 1

		all_annotations.append(ha)
	    '''

        plt.pause(0.0001)

	pickle.dump(store_results, open('stored_predictions.p','a'))
	file_name=open('stored_predictions.txt','a')
	file_name.write(str(store_results))
	file_name.write("\n")
	file_name.close()

        if metrics == 1:
            if first_time:
                annotations = np.array(results)
                first_time = False
            else:
                annotations=np.hstack((annotations,np.array(results)))


	hogs_temp = np.array(np.array(temp))
        


if __name__ == '__main__':
    laser_listener()






      
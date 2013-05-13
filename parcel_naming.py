import nibabel as nb
import numpy as np
from collections import defaultdict
from lxml import etree
import os, sys

# The following code was adapted from Satra Gosh's sad_figures.py script
# located at https://github.com/satra/sad/blob/master/sad_figures.py

# get cluster coordinates caculate the volume and the center of mass
# of the brain regions in img

def get_region_CoM(img, affine):
    coords = defaultdict(dict)

    # determine the unique regions
    labels = np.setdiff1d(np.unique(img.ravel()), [0])

    for label in labels:

        # calculate the volume of the region
        coords[label]["Vol"]=np.sum(img==label)

        # calculate the center of mass (CoM) of the region
        coords[label]["CoM"]=np.dot(affine,\
            np.hstack((np.mean(np.asarray(np.nonzero(img==label)),\
            axis = 1),1)))[:3].tolist()

    return (coords)

# convert coordinates from one image to another, coords'=inv(A2)*A1*coords
def most_common(lst):
    return max(set(lst), key=lst.count)

def image_downsample_voting(img, affine, down_img_template, down_img_affine):
    down_vals=defaultdict(list)

    old_coords=np.array(np.nonzero(img),dtype="int").T
    for i in range(np.shape(old_coords)[0]):
        new_coords=[str(int(c)) for c in np.round(\
            np.dot(np.linalg.inv(down_img_affine),\
            np.dot(affine,np.hstack((old_coords[i,:],1)))),decimals=0)[:3]]
        down_vals["_".join(new_coords)].append(img[tuple(old_coords[i,:])])

    new_img=np.zeros(np.shape(down_img_template),dtype="int")
    for k in down_vals.keys():
        idx=tuple([ int(n) for n in k.split("_")])
        new_img[idx]=most_common(down_vals[k])

    return (new_img)

def read_and_conform_atlas(atlas_file,atlas_label_file,\
        template_img,template_affine):

    atlas_labels=defaultdict()

    print "Reading in the atlas labels: %s"%(atlas_label_file)
    lbl_root=etree.parse(atlas_label_file)
    for l in lbl_root.getiterator():
        if l.get("index"):
            atlas_labels[int(l.get("index"))+1]=l.text.replace(',',';')
    atlas_labels[0]="None"
    print "Read in the atlas %s"%(atlas_file)
    # lets read in the Harvord Oxford Cortical map
    atlas_nii=nb.load(atlas_file)
    atlas_img=atlas_nii.get_data()

    print "Downsample the atlas"
    # resample the atlas to conform to parcels
    atlas_conform=image_downsample_voting(atlas_img, atlas_nii.get_affine(),\
                                   template_img, \
                                   template_affine);

    #print "Write out the downsampled atlas"
    #out_img=nb.Nifti1Image(atlas_conform,template_affine);
    #out_img.set_data_dtype("int16")
    #out_img.to_filename("atlas_conf.nii.gz")

    return (atlas_labels,atlas_conform)

def main():

    try:
        fsl_path=os.environ['FSL_DIR']
    except KeyError:
        print "FSL_DIR is not set in the environment, is FSL installed?"
        sys.exit()

    atlas_cfg={\
      "Talairach Daemon":("Talairach-relabeled.xml",\
        os.path.join(fsl_path,"data/atlases/Talairach/Talairach-labels-2mm.nii.gz")),\
      "HarvardOxford Cortical":("HarvardOxford-Cortical-relabeled.xml",\
        os.path.join(fsl_path,"data/atlases/HarvardOxford/HarvardOxford-cort-maxprob-thr25-2mm.nii.gz")),\
      "HarvardOxford Subcortical":("HarvardOxford-Subcortical-relabeled.xml",\
        os.path.join(fsl_path,"data/atlases/HarvardOxford/HarvardOxford-sub-maxprob-thr25-2mm.nii.gz")),\
      "Jeulich Histological":("Juelich-relabeled.xml",\
         os.path.join(fsl_path,"data/atlases/Juelich/Juelich-maxprob-thr25-2mm.nii.gz")),\
      "MNI Structural":("MNI-relabeled.xml",\
        os.path.join(fsl_path,"data/atlases/MNI/MNI-maxprob-thr25-2mm.nii.gz"))}

    if len(sys.argv) < 4:
        print "number of arguements %d"%(len(sys.argv))
        print "Usage %s <parcellation filename> <outname> <10,20,30,...>"%(sys.argv[0])
        sys.exit()

    parcel_filename=sys.argv[1]
    parcel_outname=sys.argv[2]
    parcel_vals=[int(n) for n in sys.argv[3].split(',')]

    print "%s called with %s, %s, %s"%(sys.argv[0],parcel_filename,\
        parcel_outname,",".join([str(i) for i in parcel_vals]))

    print "Read in the parcellation results %s"%(parcel_filename)
    # lets read in the parcellation results that we want to label
    parcels_nii=nb.load(parcel_filename)
    parcels_img=parcels_nii.get_data()

    if len(parcel_vals) != np.shape(parcels_img)[3]:
        print "Length of parcel values (%d) != number of parcel images (%d)"%( \
            len(parcel_vals),np.shape(parcels_img)[3])
        sys.exit()
    else:
        print "Length of parcel values (%d) == number of parcel images (%d)"%( \
            len(parcel_vals),np.shape(parcels_img)[3])
    #HO_atlas=read_and_conform_atlas(os.path.join(fsl_path,\
        #'data/atlases/HarvardOxford/HarvardOxford-cort-maxprob-thr25-1mm.nii.gz'),\
        #parcels_img[:,:,:,0],parcels_nii.get_affine())

    atlases=defaultdict()

    # read in the atlases 
    for k in atlas_cfg.keys():
        atlases[k]=read_and_conform_atlas(atlas_cfg[k][1],atlas_cfg[k][0],\
            parcels_img[:,:,:,0],parcels_nii.get_affine())

    #for p in [0]:
    for p in range(np.shape(parcels_img)[3]):
        fid=open("%s_names_%d.csv"%(parcel_outname,parcel_vals[p]),"w")
        # print out the header
        fid.write("ROI number, volume, center of mass")
        for atlas in atlases:
            fid.write(",%s"%(atlas))
        fid.write("\n")

        p_c=get_region_CoM(parcels_img[:,:,:,p],parcels_nii.get_affine())
        for p_k in p_c.keys():
            fid.write("%d, %d, (%2.1f;%2.1f;%2.1f)"%(p_k,p_c[p_k]["Vol"],
                p_c[p_k]["CoM"][0],p_c[p_k]["CoM"][1],p_c[p_k]["CoM"][2]))
            for atlas in atlases.keys():
                fid.write(",")
                atlas_vals=atlases[atlas][1][np.nonzero(parcels_img[:,:,:,p]==p_k)]
                # calculate a histogram of the values
                atlas_hist=[(n,round(float(sum(atlas_vals==n))/float(len(atlas_vals)),2)) \
                    for n in np.unique(atlas_vals)]
                atlas_hist=sorted(atlas_hist,key=lambda f: -f[1])
                for h in atlas_hist:
                    if h[1] > 0.1:
                        fid.write("[\"%s\": %2.2f]"%(atlases[atlas][0][h[0]],h[1]))
            fid.write("\n")
        fid.close()

if __name__ == "__main__":
    main()

#%run parcel_naming.py tcorr05_2level_all.nii.gz tcorr05_2level '10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220,230,240,250,260,270,280,290,300,350,400,450,500,550,600,650,700,750,800,850,900,950'
#%run parcel_naming.py scorr05_2level_all.nii.gz scorr05_2level '10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220,230,240,250,260,270,280,290,300,350,400,450,500,550,600,650,700,750,800,850,900,950'
#%run parcel_naming.py tcorr05_mean_all.nii.gz tcorr05_mean '10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220,230,240,250,260,270,280,290,300,350,400,450,500,550,600,650,700,750,800,850,900,950'
#%run parcel_naming.py scorr05_mean_all.nii.gz scorr05_mean '10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220,230,240,250,260,270,280,290,300,350,400,450,500,550,600,650,700,750,800,850,900,950'
#%run parcel_naming.py random_all.nii.gz random '10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220,230,240,250,260,270,280,290,300,350,400,450,500,550,600,650,700,750,800,850,900,950'

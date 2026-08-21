import pathlib
import nibabel as nib
import subprocess
import numpy as np
import torchio as tio
import pandas as pd
from skimage import measure
from sklearn.mixture import GaussianMixture, BayesianGaussianMixture
from scipy.ndimage import binary_dilation, generate_binary_structure, label as ndi_label
import concurrent.futures


def calc_mean_value_for_label(volume,label, mask):
    if np.sum(mask == label) == 0:
        return np.nan    
    return np.mean(volume[mask == label])


def save_segmentation(clf, out_name, mask_t1_vals, X, mask_indices, mask_obj, subjects_dir):
    """
    Save segmentation result from a clustering model.

    Parameters:
        clf : clustering model (e.g. GaussianMixture or BayesianGaussianMixture)
        out_name : output filename (e.g. 'lh_choroid_gmmb_mask.nii.gz')
        mask_t1_vals : intensity values from the T1 image within the mask
        X : feature array (e.g. intensity values reshaped to (-1, 1))
        mask_indices : tuple of indices (i, j, k) where the mask is 1
        mask_obj : nibabel image object (used to access the affine)
        subjects_dir : base directory of the subjects
        subj : subject identifier
    """
    # Initialize an empty image volume
    new_img = np.zeros((mask_obj.get_fdata().shape))

    # Predict labels and decide which cluster corresponds to the choroid plexus
    predictions = clf.predict(X)
    if np.mean(mask_t1_vals[predictions == 1]) > np.mean(mask_t1_vals[predictions == 0]):
        choroid_ind = np.where(predictions == 1)[0]
    else:
        choroid_ind = np.where(predictions == 0)[0]

    choroid_coords = (mask_indices[0][choroid_ind],
                    mask_indices[1][choroid_ind],
                    mask_indices[2][choroid_ind])
    new_img[choroid_coords] = 1
    img_obj = nib.Nifti1Image(new_img, mask_obj.affine)
    out_path = f'{subjects_dir}/{out_name}'
    nib.save(img_obj, out_path)


def susan(input_img):
    """
    Run the 'susan' command on the given image.
    The command assumes the image file has a '.nii.gz' extension.
    """
    base_img = input_img.split('.nii')[0]
    cmd = f'susan {base_img}.nii.gz 1 1 3 1 0 {base_img}_susan.nii.gz'
    subprocess.run(cmd, shell=True, check=True)


freesurfer_labels = {
    17: "left hippocampus",
    53: "right hippocampus",
    2: "left cerebral white matter",
    # 3: "Left-Gray-Matter",
    41: "right cerebral white matter",
    # 42: "Right-Gray-Matter",
    11: "left caudate nucleus",
    50: "right caudate nucleus",
    13:  "left pallidum",
    52:  "right pallidum",
    12: "left putamen",
    51: "right putamen",
}

results_list = []

root_dir = pathlib.Path("/data04/ASD_Li_lab/")

for site in root_dir.iterdir():
    if not site.is_dir():
        continue

    if site.name not in ["ASD_baseline", "HC_Time2", "TD_Time1"]:
        continue
    
    for subj_dir in site.iterdir():
        if not subj_dir.is_dir():
            continue

        subject = subj_dir.name
        
        anat_dir = subj_dir / "anat"
        dwi_dir = subj_dir / "dwi"
        
        # Frangi filter
        pvs_file = anat_dir / f"{subject}_pvs.nii.gz"
        t1_seg = anat_dir / subject / "mri" / "aparc+aseg.mgz"
        
        pvs_img = nib.load(str(pvs_file))
        pvs_data = pvs_img.get_fdata()
        
        t1_seg_img = nib.load(str(t1_seg))
        t1_seg_data = t1_seg_img.get_fdata()

        subject_row = {'subject': subject, 'category': site.name}
        for fs_id, fs_name in freesurfer_labels.items():
            if "white matter" not in fs_name:
                continue
            
            roi_mask = (t1_seg_data == fs_id)
            roi_mask = binary_dilation(roi_mask, structure=np.ones((3,3,3)), iterations=1)
            
            valid_pvs_data = pvs_data * roi_mask
            roi_vals = valid_pvs_data[valid_pvs_data > 0]
            
            if roi_vals.size == 0:
                thr = 1.0
            else:
                thr = max(np.quantile(roi_vals, 0.90), 0.1)
        
            pvs_binary = valid_pvs_data > thr
            
            label_img = measure.label(pvs_binary, connectivity=1)
            props = measure.regionprops(label_img)
            
            voxel_vol = np.prod(pvs_img.header.get_zooms()[0:3])
            min_voxels = 3
            
            total_pvs_vol = 0
            total_pvs_count = 0
            
            for prop in props:
                if prop.area >= min_voxels:
                    total_pvs_vol += prop.area * voxel_vol
                    total_pvs_count += 1
                
            subject_row['PVS volume of '+fs_name+' mm^3'] = total_pvs_vol
            subject_row['PVS number of '+fs_name] = total_pvs_count

        # FreeWater
        fw_file = dwi_dir.rglob("*_FW.nii.gz")
        fw_file = list(fw_file)[0]
        
        seg_in_dwi = dwi_dir / f"{subject}_aparc_dwi.nii.gz"
        
        seg_dwi_img = nib.load(str(seg_in_dwi))
        seg_dwi_data = seg_dwi_img.get_fdata()
        
        fw_img = nib.load(str(fw_file))
        fw_data = fw_img.get_fdata()
        
        # FA
        fa_file = dwi_dir / "DTI" / f"{subject}_FA.nii.gz"
        fa_img = nib.load(str(fa_file))
        fa_data = fa_img.get_fdata()
        
        # MD
        md_file = dwi_dir / "DTI" / f"{subject}_MD.nii.gz"
        md_img = nib.load(str(md_file))
        md_data = md_img.get_fdata()
        
        # AD
        ad_file = dwi_dir / "DTI" / f"{subject}_AD.nii.gz"
        ad_img = nib.load(str(ad_file))
        ad_data = ad_img.get_fdata()
        
        # RA
        rd_file = dwi_dir / "DTI" / f"{subject}_RA.nii.gz"
        rd_img = nib.load(str(rd_file))
        rd_data = rd_img.get_fdata()
        
        # RD
        rd_file = dwi_dir / "DTI" / f"{subject}_RD.nii.gz"
        rd_img = nib.load(str(rd_file))
        rd_data = rd_img.get_fdata()
        
        for fs_id, fs_name in freesurfer_labels.items():
            subject_row['FW of '+fs_name] = calc_mean_value_for_label(fw_data, fs_id, seg_dwi_data)
            subject_row['FA of '+fs_name] = calc_mean_value_for_label(fa_data, fs_id, seg_dwi_data)
            subject_row['MD of '+fs_name] = calc_mean_value_for_label(md_data, fs_id, seg_dwi_data)
            subject_row['AD of '+fs_name] = calc_mean_value_for_label(ad_data, fs_id, seg_dwi_data)
            subject_row['RD of '+fs_name] = calc_mean_value_for_label(rd_data, fs_id, seg_dwi_data)
        
        # DTI-ALPS
        dti_file = (dwi_dir / "DTI").glob("*dwi_DTI.nrrd")
        dti_file = list(dti_file)[0]
        subject_dti = tio.Subject(
            dti = tio.ScalarImage(str(dti_file)),
            roi_A = tio.ScalarImage(str(dwi_dir / "ROI" / f"{subject}_doctorA_ROI.nrrd")),
            roi_B = tio.ScalarImage(str(dwi_dir / "ROI" / f"{subject}_doctorB_ROI.nrrd")),
            roi_C = tio.ScalarImage(str(dwi_dir / "ROI" / f"{subject}_doctorC_ROI.nrrd")),
        )
        flatten_dti = subject_dti['dti'].data.reshape(3,3,-1).permute(2,0,1)
        asso_A = flatten_dti[(subject_dti['roi_A'].data==1).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        proj_A = flatten_dti[(subject_dti['roi_A'].data==2).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        dti_alps_A = float(asso_A[0,0]+proj_A[0,0])/(asso_A[2,2]+proj_A[1,1])
        
        asso_B = flatten_dti[(subject_dti['roi_B'].data==1).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        proj_B = flatten_dti[(subject_dti['roi_B'].data==2).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        dti_alps_B = float(asso_B[0,0]+proj_B[0,0])/(asso_B[2,2]+proj_B[1,1])
        
        asso_C = flatten_dti[(subject_dti['roi_C'].data==1).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        proj_C = flatten_dti[(subject_dti['roi_C'].data==2).reshape(-1),:,:].reshape(-1,3,3).mean(0)
        dti_alps_C = float(asso_C[0,0]+proj_C[0,0])/(asso_C[2,2]+proj_C[1,1])
        
        subject_row['dti_alps_A'] = np.mean([dti_alps_A])
        subject_row['dti_alps_B'] = np.mean([dti_alps_B])
        subject_row['dti_alps_C'] = np.mean([dti_alps_C])
        
        subject_row['dti_alps_mean'] = np.mean([dti_alps_A, dti_alps_B, dti_alps_C])
        
        # the Gaussian Mixture Models
        # https://github.com/EhsanTadayon/choroid-plexus-segmentation
        t1_path = anat_dir / subject / "mri" / "T1.mgz"
        T1 = nib.load(str(t1_path)).get_fdata()
        
        aseg_path = anat_dir / subject / "mri" / "aseg.mgz"
        
        print('Creating masks: choroid_ventricle_mask.nii.gz and aseg_choroid_mask.nii.gz')
        
        aseg_choroid_mask_path = anat_dir / "aseg_choroid_mask.nii.gz"
        if not aseg_choroid_mask_path.exists():
            cmd = f"mri_binarize --i {aseg_path} --match 31 63 --o {aseg_choroid_mask_path}"
            subprocess.run(cmd, shell=True, check=True)
            
        lh_choroid_ventricle_mask_path = anat_dir / "lh_choroid_ventricle_mask.nii.gz"
        if not lh_choroid_ventricle_mask_path.exists():
            cmd = f"mri_binarize --i {aseg_path} --match 4 5 31 --o {lh_choroid_ventricle_mask_path}"
            subprocess.run(cmd, shell=True, check=True)
            
        rh_choroid_ventricle_mask_path = anat_dir / "rh_choroid_ventricle_mask.nii.gz"
        if not rh_choroid_ventricle_mask_path.exists():
            cmd = f"mri_binarize --i {aseg_path} --match 43 44 63 --o {rh_choroid_ventricle_mask_path}"
            subprocess.run(cmd, shell=True, check=True)
            
        # Left hemisphere
        print('Processing left hemisphere')
        lh_gmmb_mask_path = anat_dir / "lh_choroid_gmmb_mask.nii.gz"
        
        if not lh_gmmb_mask_path.exists():
            lh_choroid_ventricle_mask_obj = nib.load(str(lh_choroid_ventricle_mask_path))
            lh_choroid_ventricle_mask = lh_choroid_ventricle_mask_obj.get_fdata()
            lh_choroid_ventricle_mask_indices = np.where(lh_choroid_ventricle_mask == 1)
            mask_t1_vals = T1[lh_choroid_ventricle_mask_indices]
            X = mask_t1_vals.reshape(-1, 1)
            bgmm_lh = BayesianGaussianMixture(n_components=2, covariance_type='full').fit(X)
            
            save_segmentation(bgmm_lh, 'lh_choroid_gmmb_mask.nii.gz', mask_t1_vals, X, lh_choroid_ventricle_mask_indices, lh_choroid_ventricle_mask_obj, anat_dir)
            
        lh_gmmb_mask_susan_path = anat_dir / "lh_choroid_gmmb_mask_susan.nii.gz"
        if not lh_gmmb_mask_susan_path.exists():
            susan(str(lh_gmmb_mask_path))
            
        lh_choroid_susan_segmentation_path = anat_dir / "lh_choroid_susan_segmentation.nii.gz"
        if not lh_choroid_susan_segmentation_path.exists():
            lh_choroid_gmmb_mask = nib.load(str(lh_gmmb_mask_path)).get_fdata()
            lh_choroid_gmmb_mask_indices = np.where(lh_choroid_gmmb_mask == 1)
            lh_choroid_gmmb_susan = nib.load(str(lh_gmmb_mask_susan_path)).get_fdata()
            susan_vals = lh_choroid_gmmb_susan[lh_choroid_gmmb_mask_indices]
            
            bgmm_susan_lh = BayesianGaussianMixture(n_components=3).fit(susan_vals.reshape(-1, 1))
            susan_predictions = bgmm_susan_lh.predict(susan_vals.reshape(-1, 1))
            means = bgmm_susan_lh.means_.flatten()
            choroid_cluster = np.argmax(means)
            
            lh_choroid_seg = np.zeros(lh_choroid_gmmb_mask.shape)
            indices = np.where(susan_predictions == choroid_cluster)
            lh_choroid_seg[(lh_choroid_gmmb_mask_indices[0][indices],
                            lh_choroid_gmmb_mask_indices[1][indices],
                            lh_choroid_gmmb_mask_indices[2][indices])] = 1
            
            lh_choroid_seg_obj = nib.Nifti1Image(lh_choroid_seg, nib.load(str(lh_gmmb_mask_path)).affine)
            nib.save(lh_choroid_seg_obj, str(anat_dir / "lh_choroid_susan_segmentation.nii.gz"))
        
        # Right hemisphere
        print('Processing right hemisphere')
        rh_gmmb_mask_path = anat_dir / "rh_choroid_gmmb_mask.nii.gz"
        if not rh_gmmb_mask_path.exists():
            rh_choroid_ventricle_mask_obj = nib.load(str(rh_choroid_ventricle_mask_path))
            rh_choroid_ventricle_mask = rh_choroid_ventricle_mask_obj.get_fdata()
            rh_choroid_ventricle_mask_indices = np.where(rh_choroid_ventricle_mask == 1)
            mask_t1_vals_rh = T1[rh_choroid_ventricle_mask_indices]
            X_rh = mask_t1_vals_rh.reshape(-1, 1)
            
            bgmm_rh = BayesianGaussianMixture(n_components=2, covariance_type='full').fit(X_rh)
            save_segmentation(bgmm_rh, 'rh_choroid_gmmb_mask.nii.gz', mask_t1_vals_rh, X_rh, rh_choroid_ventricle_mask_indices, rh_choroid_ventricle_mask_obj, anat_dir)
        
        rh_gmmb_mask_susan_path = anat_dir / "rh_choroid_gmmb_mask_susan.nii.gz"
        if not rh_gmmb_mask_susan_path.exists():
            susan(str(rh_gmmb_mask_path))
            
        rh_choroid_susan_segmentation_path = anat_dir / "rh_choroid_susan_segmentation.nii.gz"
        if not rh_choroid_susan_segmentation_path.exists():
            rh_choroid_gmmb_mask = nib.load(str(rh_gmmb_mask_path)).get_fdata()
            rh_choroid_gmmb_mask_indices = np.where(rh_choroid_gmmb_mask == 1)
            rh_choroid_gmmb_susan = nib.load(str(rh_gmmb_mask_susan_path)).get_fdata()
            susan_vals_rh = rh_choroid_gmmb_susan[rh_choroid_gmmb_mask_indices]
            
            bgmm_susan_rh = BayesianGaussianMixture(n_components=3).fit(susan_vals_rh.reshape(-1, 1))
            susan_predictions_rh = bgmm_susan_rh.predict(susan_vals_rh.reshape(-1, 1))
            means_rh = bgmm_susan_rh.means_.flatten()
            choroid_cluster_rh = np.argmax(means_rh)
            
            rh_choroid_seg = np.zeros(rh_choroid_gmmb_mask.shape)
            indices_rh = np.where(susan_predictions_rh == choroid_cluster_rh)
            rh_choroid_seg[(rh_choroid_gmmb_mask_indices[0][indices_rh],
                            rh_choroid_gmmb_mask_indices[1][indices_rh],
                            rh_choroid_gmmb_mask_indices[2][indices_rh])] = 1
            
            rh_choroid_seg_obj = nib.Nifti1Image(rh_choroid_seg, nib.load(str(rh_gmmb_mask_path)).affine)
            nib.save(rh_choroid_seg_obj, str(anat_dir / "rh_choroid_susan_segmentation.nii.gz"))
        
        choroid_susan_segmentation_path = anat_dir / "choroid_susan_segmentation.nii.gz"
        if not choroid_susan_segmentation_path.exists():
            cmd = f"fslmaths {anat_dir}/lh_choroid_susan_segmentation.nii.gz -add {anat_dir}/rh_choroid_susan_segmentation.nii.gz {choroid_susan_segmentation_path}"
            subprocess.run(cmd, shell=True, check=True)
            
        choroid_gmmb_mask_path = anat_dir / "choroid_gmmb_mask.nii.gz"
        if not choroid_gmmb_mask_path.exists():
            cmd = f"fslmaths {anat_dir}/lh_choroid_gmmb_mask.nii.gz -add {anat_dir}/rh_choroid_gmmb_mask.nii.gz {choroid_gmmb_mask_path}"
            subprocess.run(cmd, shell=True, check=True)
            
        choroid_gmmb_susan_img = nib.load(str(choroid_susan_segmentation_path))
        choroid_gmmb_susan_data = choroid_gmmb_susan_img.get_fdata()
        choroid_gmmb_susan_voxelsize = choroid_gmmb_susan_img.header.get_zooms()[0] * choroid_gmmb_susan_img.header.get_zooms()[1] * choroid_gmmb_susan_img.header.get_zooms()[2]
        subject_row['Choroid plexus volume (GMMB + SUSAN) (mm3)'] = (choroid_gmmb_susan_data > 0).sum() * choroid_gmmb_susan_voxelsize            
        
        results_list.append(subject_row)
        
        if len(results_list) % 5 == 0:
            pd.DataFrame(results_list).to_csv("/data04/ASD_Li_lab/results/glymphatic_system_metrics_intermediate.csv", index=False)

df = pd.DataFrame(results_list)
df.to_csv("/data04/ASD_Li_lab/results/glymphatic_system_metrics.csv", index=False)

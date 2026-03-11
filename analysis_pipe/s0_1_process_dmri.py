import os
import shutil
import glob
import subprocess
from multiprocessing import Pool, cpu_count
import nibabel as nib


def convert_to_nrrd(nifti_file, bval_file, bvec_file, output_dir):
    slicer_path = '/data01/software/Slicer-5.2.2-linux-amd64/Slicer'
    slicer_cli_module = '/data01/software/Slicer-5.2.2-linux-amd64/lib/Slicer-5.2/cli-modules/DWIConvert'
    
    output_volume = os.path.join(output_dir, os.path.basename(nifti_file).replace('.nii.gz', '.nrrd'))

    command = [
        slicer_path,
        '--launch', slicer_cli_module,
        '--conversionMode', 'FSLToNrrd',
        '--transposeInputBVectors',
        '--outputVolume', output_volume,
        '--smallGradientThreshold', '0.2',
        '--inputBValues', bval_file,
        '--inputBVectors', bvec_file,
        '--fslNIFTIFile', nifti_file,
        '--allowLossyConversion',
        '--writeProtocolGradientsFile'
    ]
    
    subprocess.run(command)


CNN_masking_model_folder = '/data01/software/CNN-Diffusion-MRIBrain-Segmentation/model_folder'
ORG_atlas_folder = '/data01/software/ORG-Atlases'
slicer_path = '/data01/software/Slicer-5.2.2-linux-amd64/Slicer'
fibermeasurement_module = f'{slicer_path} --launch /data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/FiberTractMeasurements'

input_dir = "/data04/ASD_Li_lab/2B_pre"


def process_subject(args):
    site, subject = args
    site_path = os.path.join(input_dir, site)
    subject_path = os.path.join(site_path, subject)

    print(f"[INFO] Start processing: site={site}, subject={subject}")

    if not os.path.isdir(subject_path):
        print(f"[WARN] Subject path is not dir, skip: {subject_path}")
        return

    dwi_dir = os.path.join(subject_path, "dwi")
    if not os.path.exists(dwi_dir) or not os.path.isdir(dwi_dir):
        print(f"[WARN] No dwi dir for subject, skip: {subject_path}")
        return

    dwi_files = sorted(glob.glob(os.path.join(dwi_dir, "*PA*_dwi.nii.gz")))[0]
    if not dwi_files:
        dwi_files = sorted(glob.glob(os.path.join(dwi_dir, "*_dwi.nii.gz")))[0]
        if not dwi_files:
            print(f"[WARN] No dwi file for subject, skip: {subject_path}")
            return
    
    base_name = os.path.basename(dwi_files).replace('.nii.gz', '')

    # convert to nrrd
    dwi_nrrd = dwi_files.replace('.nii.gz', '.nrrd')
    if not os.path.exists(dwi_nrrd):
        convert_to_nrrd(
            dwi_files,
            dwi_files.replace('.nii.gz', '.bval'),
            dwi_files.replace('.nii.gz', '.bvec'),
            dwi_dir
        )
        
    # motion correct
    motion_corrected_dir = os.path.join(dwi_dir, "corrected_masked")
    os.makedirs(motion_corrected_dir, exist_ok=True)
    
    qced_file = os.path.join(motion_corrected_dir, f"{base_name}_QCed.nrrd")
    if not os.path.exists(qced_file):
        protocol_path = '/home/haolin/Research/Preprocess/dtiprepprotocalonlyeddy.xml'
                
        command = ['/home/haolin/Research/Preprocess/DTIPrep-1.2.11/bin/DTIPrep', 
                '--DWINrrdFile', dwi_nrrd, 
                '--default', 
                '--check', 
                '--xmlProtocol', protocol_path,
                '--numberOfThreads', '32', 
                '--outputFolder', motion_corrected_dir
                ]
        subprocess.run(command)
        
    # run cnn mask
    
    
    # CNN masking
    txt_file = os.path.join(motion_corrected_dir, f"{subject}.txt")
    with open(txt_file, 'w') as f:
        f.write(qced_file + '\n')
        
    brain_mask_nifti = os.path.join(motion_corrected_dir, f"{base_name}_QCed_bse-multi_BrainMask.nii.gz")
    
    if not os.path.exists(brain_mask_nifti):
        command = f"""
        export ANTSPATH=/data01/software/ants/bin &&
        export PATH=${{ANTSPATH}}:$PATH &&
        /data01/software/miniconda3/py310_23.3.1-0/envs/dmri_seg/bin/python \
            /data01/software/CNN-Diffusion-MRIBrain-Segmentation/pipeline/dwi_masking.py \
            -i {txt_file} -f {CNN_masking_model_folder}
        """
        subprocess.run(command, shell=True)
    
    brain_mask_nhdr = os.path.join(motion_corrected_dir, f"{base_name}_QCed_bse-multi_BrainMask.nhdr")
    
    if not os.path.exists(brain_mask_nhdr):
        # mask -> nhdr
        command = [
            '/data06/yijie/miniconda3/envs/wma/bin/python',
            '/home/yijie/conversion/conversion/nhdr_write.py',
            '--nifti', brain_mask_nifti,
            '--nhdr', brain_mask_nhdr
        ]
        subprocess.run(command)
    
    tractography_dir = os.path.join(dwi_dir, "tractography")
    os.makedirs(tractography_dir, exist_ok=True)
    
    # UKF tractography
    tractography_path = os.path.join(tractography_dir, f"{subject}.vtk")
    
    if not os.path.exists(tractography_path):
        command = [
            '/data01/software/Slicer-5.2.2-linux-amd64/Slicer',
            '--launch',
            '/data01/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/UKFTractography/lib/Slicer-5.2/cli-modules/UKFTractography',
            '--numThreads', '80',
            '--numTensor', '2',
            '--dwiFile', qced_file,
            '--maskFile', brain_mask_nhdr,
            '--tracts', tractography_path,
            '--seedingThreshold', '0.1',
            '--stoppingFA', '0.08',
            '--stoppingThreshold', '0.06',
            '--seedsPerVoxel', '3',
            '--recordFA',
            '--freeWater',
            '--recordTrace',
            '--recordTensors',
            '--recordFreeWater'
        ]
        subprocess.run(command)
    
    wma_dir = os.path.join(dwi_dir, "WMA")
    os.makedirs(wma_dir, exist_ok=True)
    my_wma_script = "/data04/ASD_Li_lab/scripts/my_wm_apply.sh"
    
    if not os.path.exists(os.path.join(wma_dir, subject, "AnatomicalTracts", "diffusion_measurements_anatomical_tracts.csv")):
        # run WMA
        # command = f"""
        # . /data06/yijie/miniconda3/etc/profile.d/conda.sh &&
        # conda activate wma &&
        # {my_wma_script} \
        
        command = f"""
        . /data06/yijie/miniconda3/etc/profile.d/conda.sh &&
        conda activate wma &&
        /data01/software/whitematteranalysis/bin/wm_apply_ORG_atlas_to_subject.sh \
        -i {tractography_path} \
        -o {wma_dir} \
        -a {ORG_atlas_folder} \
        -s {slicer_path} \
        -n {4} -c 2 -x 1 -d 1 \
        -m "{fibermeasurement_module}"
        """
        subprocess.run(command, shell=True, executable='/bin/bash')

    print(f"[INFO] Finished processing: site={site}, subject={subject}")

if __name__ == "__main__":

    # subject_list = []
    # for site in os.listdir(input_dir):
    #     site_path = os.path.join(input_dir, site)
    #     if not os.path.isdir(site_path):
    #         continue

    #     for subject in os.listdir(site_path):
    #         subject_path = os.path.join(site_path, subject)
    #         if not os.path.isdir(subject_path):
    #             continue
            
    #         dwi_dir = os.path.join(subject_path, "dwi")
    #         if not os.path.exists(dwi_dir) or not os.path.isdir(dwi_dir):
    #             continue

    #         dwi_files = glob.glob(os.path.join(dwi_dir, "*_dwi.nii.gz"))
    #         if len(dwi_files) == 0:
    #             continue

    #         subject_list.append((site, subject))

    # print(f"[INFO] Total subjects to process: {len(subject_list)}")
    subject_list = [("HC_Time2", "HC0124"), ("HC_Time2", "HC071"), ("HC_Time2", "HC077"), ("HC_Time2", "HC093")]

    NUM_WORKERS = min(10, cpu_count())

    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(process_subject, subject_list)
    # process_subject(('HC_Time2', 'HC0142'))

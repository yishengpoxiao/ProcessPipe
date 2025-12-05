import os
import shutil
import glob
import subprocess
from multiprocessing import Pool, cpu_count


def convert_to_nrrd(nifti_file, bval_file, bvec_file, output_dir):
    slicer_path = '/data/software/Slicer-5.2.2-linux-amd64/Slicer'
    slicer_cli_module = '/data/software/Slicer-5.2.2-linux-amd64/lib/Slicer-5.2/cli-modules/DWIConvert'
    
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

CNN_masking_model_folder = '/data/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/model_folder'
ORG_atlas_folder = '/data/software/ORG-Atlases'
slicer_path = '/data/software/Slicer-5.2.2-linux-amd64/Slicer'
fibermeasurement_module = f'{slicer_path} --launch /data/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/SlicerDMRI/lib/Slicer-5.2/cli-modules/FiberTractMeasurements'

input_dir = "/data/private_data/ASD_Li_lab"

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

    dwi_files = glob.glob(os.path.join(dwi_dir, "*_dwi.nii.gz"))

    # dwidenoise -> dwipreprocess -> bias correction -> gradcheck -> NRRD -> CNN masking -> UKF -> WMA
    if len(dwi_files) == 1:
        dwi_file = dwi_files[0]
        
        mrtrix_temp_dir = os.path.join(dwi_dir, "mrtrix_temp")
        os.makedirs(mrtrix_temp_dir, exist_ok=True)
        
        mif_file = os.path.join(mrtrix_temp_dir, os.path.basename(dwi_file).replace('.nii.gz', '.mif'))
        
        command = [
            "mrconvert",
            dwi_file,
            mif_file,
            "-fslgrad",
            dwi_file.replace('.nii.gz', '.bvec'),
            dwi_file.replace('.nii.gz', '.bval'),
            "-json_import",
            dwi_file.replace('.nii.gz', '.json'),
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        # denoise
        denoised_mif = os.path.join(mrtrix_temp_dir, os.path.basename(dwi_file).replace('.nii.gz', '_den.mif'))
        command = [
            "dwidenoise",
            mif_file,
            denoised_mif,
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        # preprocess
        preprocessed_mif = os.path.join(mrtrix_temp_dir, f"{subject}_dwi_preproc.mif")
        command = [
            "dwifslpreproc",
            denoised_mif,
            preprocessed_mif,
            "-rpe_none",
            "-pe_dir", "PA",
            "-eddy_options", " --slm=linear ",
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
    elif len(dwi_files) == 2:
        try:
            PA_dwi_file = [f for f in dwi_files if 'PA_' in f][0]
            AP_dwi_file = [f for f in dwi_files if 'AP_' in f][0]
        except IndexError:
            print(f"[WARN] Cannot find PA_/AP_ dwi files for subject, skip: {subject_path}")
            return
        
        mrtrix_temp_dir = os.path.join(dwi_dir, "mrtrix_temp")
        os.makedirs(mrtrix_temp_dir, exist_ok=True)
        PA_mif_file = os.path.join(mrtrix_temp_dir, os.path.basename(PA_dwi_file).replace('.nii.gz', '.mif'))
        AP_mif_file = os.path.join(mrtrix_temp_dir, os.path.basename(AP_dwi_file).replace('.nii.gz', '.mif'))
        
        command = [
            "mrconvert",
            PA_dwi_file,
            PA_mif_file,
            "-fslgrad",
            PA_dwi_file.replace('.nii.gz', '.bvec'),
            PA_dwi_file.replace('.nii.gz', '.bval'),
            "-json_import",
            PA_dwi_file.replace('.nii.gz', '.json'),
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        command = [
            "mrconvert",
            AP_dwi_file,
            AP_mif_file,
            "-fslgrad",
            AP_dwi_file.replace('.nii.gz', '.bvec'),
            AP_dwi_file.replace('.nii.gz', '.bval'),
            "-json_import",
            AP_dwi_file.replace('.nii.gz', '.json'),
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        # denoise
        denoised_PA_mif = os.path.join(mrtrix_temp_dir, os.path.basename(PA_dwi_file).replace('.nii.gz', '_den.mif'))
        command = [
            "dwidenoise",
            PA_mif_file,
            denoised_PA_mif,
            "-nthreads", "80"
        ]
        subprocess.run(command)
        denoised_AP_mif = os.path.join(mrtrix_temp_dir, os.path.basename(AP_dwi_file).replace('.nii.gz', '_den.mif'))
        command = [
            "dwidenoise",
            AP_mif_file,
            denoised_AP_mif,
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        # cat files
        cat_mif = os.path.join(mrtrix_temp_dir, f"{subject}_2pe_dwi.mif")
        command = [
            "mrcat",
            denoised_PA_mif,
            denoised_AP_mif,
            cat_mif,
            "-axis", "3",
            "-nthreads", "80"
        ]
        subprocess.run(command)
        
        # preprocess
        preprocessed_mif = os.path.join(mrtrix_temp_dir, f"{subject}_dwi_preproc.mif")
        command = [
            "dwifslpreproc",
            cat_mif,
            preprocessed_mif,
            "-rpe_header",
            "-eddy_options", " --slm=linear ",
            "-nthreads", "80"
        ]
        subprocess.run(command)

    else:
        print(f"[WARN] dwi_files != 1 or 2, skip subject: {subject_path}")
        return
    
    # bias correction
    biascorrected_mif = os.path.join(mrtrix_temp_dir, f"{subject}_dwi_preproc_biascorr.mif")
    command = [
        "dwibiascorrect",
        "ants",
        preprocessed_mif,
        biascorrected_mif,
        "-nthreads", "80"
    ]
    subprocess.run(command)
    
    processed_dir = os.path.join(dwi_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    
    # grad check
    command = [
        "dwigradcheck",
        biascorrected_mif,
        "-export_grad_fsl",
        os.path.join(processed_dir, f"{subject}_dwi_processed.bvec"),
        os.path.join(processed_dir, f"{subject}_dwi_processed.bval"),
        "-nthreads", "80"
    ]
    subprocess.run(command)
    
    # mif -> nifti
    processed_nifti = os.path.join(processed_dir, f"{subject}_dwi_processed.nii.gz")
    command = [
        "mrconvert",
        biascorrected_mif,
        processed_nifti,
        "-nthreads", "80"
    ]
    subprocess.run(command)
    
    # nifti -> nrrd
    convert_to_nrrd(
        processed_nifti,
        os.path.join(processed_dir, f"{subject}_dwi_processed.bval"),
        os.path.join(processed_dir, f"{subject}_dwi_processed.bvec"),
        processed_dir
    )
    
    dwi_nrrd = os.path.join(processed_dir, f"{subject}_dwi_processed.nrrd")
    
    # CNN masking
    txt_file = os.path.join(processed_dir, f"{subject}.txt")
    with open(txt_file, 'w') as f:
        f.write(dwi_nrrd + '\n')
    
    command = f"""
    export ANTSPATH=/data/software/ANTs/bin &&
    export PATH=${{ANTSPATH}}:$PATH &&
    /data/software/miniconda3/envs/dmri_seg/bin/python \
        /data/software/CNN-Diffusion-MRIBrain-Segmentation-1.0/pipeline/dwi_masking.py \
        -i {txt_file} -f {CNN_masking_model_folder}
    """
    subprocess.run(command, shell=True)
    
    brain_mask_nifti = os.path.join(processed_dir, f"{subject}_dwi_processed_bse-multi_BrainMask.nii.gz")
    brain_mask_nhdr = os.path.join(processed_dir, f"{subject}_dwi_processed_bse-multi_BrainMask.nhdr")
    
    # mask -> nhdr
    command = [
        '/data/software/miniconda3/envs/wma/bin/python',
        '/data/software/conversion/conversion/nhdr_write.py',
        '--nifti', brain_mask_nifti,
        '--nhdr', brain_mask_nhdr
    ]
    subprocess.run(command)
    
    tractography_dir = os.path.join(dwi_dir, "tractography")
    os.makedirs(tractography_dir, exist_ok=True)
    
    # UKF tractography
    tractography_path = os.path.join(tractography_dir, f"{subject}.vtk")
    
    command = [
        '/data/software/Slicer-5.2.2-linux-amd64/Slicer',
        '--launch',
        '/data/software/Slicer-5.2.2-linux-amd64/NA-MIC/Extensions-31382/UKFTractography/lib/Slicer-5.2/cli-modules/UKFTractography',
        '--numThreads', '80',
        '--numTensor', '2',
        '--dwiFile', dwi_nrrd,
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
    
    # run WMA
    command = f"""
    . /data/software/miniconda3/etc/profile.d/conda.sh &&
    conda activate wma &&
    /data/software/whitematteranalysis/bin/wm_apply_ORG_atlas_to_subject.sh \
    -i {tractography_path} \
    -o {wma_dir} \
    -a {ORG_atlas_folder} \
    -s {slicer_path} \
    -n {8} -c 2 -x 1 -d 1 \
    -m "{fibermeasurement_module}"
    """
    subprocess.run(command, shell=True, executable='/bin/bash')

    print(f"[INFO] Finished processing: site={site}, subject={subject}")

if __name__ == "__main__":

    subject_list = []
    for site in os.listdir(input_dir):
        site_path = os.path.join(input_dir, site)
        if not os.path.isdir(site_path):
            continue

        for subject in os.listdir(site_path):
            subject_path = os.path.join(site_path, subject)
            if not os.path.isdir(subject_path):
                continue
            
            dwi_dir = os.path.join(subject_path, "dwi")
            if not os.path.exists(dwi_dir) or not os.path.isdir(dwi_dir):
                continue

            dwi_files = glob.glob(os.path.join(dwi_dir, "*_dwi.nii.gz"))
            if len(dwi_files) == 0:
                continue

            subject_list.append((site, subject))

    print(f"[INFO] Total subjects to process: {len(subject_list)}")

    NUM_WORKERS = min(4, cpu_count())

    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(process_subject, subject_list)

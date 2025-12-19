"""
1. exp dti_fa
2. fa affine reg to mni
3. gqi -> mni
4. tracking
"""


from pathlib import Path
import subprocess
from joblib import Parallel, delayed


root_dir = Path("/data/dataset/FiberDataHub")
refer_img = "/data/yijie/Tractography/resources/MNI_FA_template.nii.gz"


def export_dti_fa(subj_dir):
    gqi_dirs = list(subj_dir.glob("*/dwi/gqi"))

    for gqi_dir in gqi_dirs:
        dwi_dir = gqi_dir.parent
        
        gqi_files = list(gqi_dir.glob("*.gqi.fz"))
        
        dti_metrics_dir = dwi_dir / "dti"
        dti_metrics_dir.mkdir(parents=True, exist_ok=True)
        
        for gqi_file in gqi_files:
            exported_fa = dti_metrics_dir / (gqi_file.name + ".dti_fa.nii.gz")
            
            fa_file_orig = gqi_file.parent / (gqi_file.name + ".dti_fa.nii.gz")
            
            if not exported_fa.exists() and not fa_file_orig.exists():
                cmd = [
                    "/data/yijie/software/dsi-studio/dsi_studio",
                    "--action=exp",
                    "--source={}".format(gqi_file),
                    "--export=dti_fa",
                ]
                subprocess.run(cmd)
                
            # Move the exported file to dti_metrics_dir
            
            if not exported_fa.exists() and fa_file_orig.exists():
                fa_file_orig.rename(exported_fa)


def register_fa_to_mni(subj_dir):
    dti_dirs = list(subj_dir.glob("*/dwi/dti"))
    
    for dti_dir in dti_dirs:
        fa_files = list(dti_dir.glob("*.gqi.fz.dti_fa.nii.gz"))
        
        dwi_dir = dti_dir.parent
        
        reg_dir = dwi_dir / "transform"
        reg_dir.mkdir(parents=True, exist_ok=True)
        
        for fa_file in fa_files:
            mapping_file = reg_dir / (fa_file.name + ".to_mni.mz")
            
            if not mapping_file.exists():
                cmd = [
                    "/data/yijie/software/dsi-studio/dsi_studio",
                    "--action=reg",
                    "--source={}".format(fa_file),
                    "--to={}".format(refer_img),
                    "--skip_nonlinear=1",
                    "--output_mapping={}".format(mapping_file),
                    "--output={}".format(reg_dir / (fa_file.name + ".mni.nii.gz")),
                ]
                subprocess.check_call(cmd)
                
                
def register_gqi_to_mni(subj_dir):
    gqi_dirs = list(subj_dir.glob("*/dwi/gqi"))
    
    for gqi_dir in gqi_dirs:
        gqi_files = list(gqi_dir.glob("*.gqi.fz"))
        
        dwi_dir = gqi_dir.parent
        
        reg_dir = dwi_dir / "transform"
        reg_dir.mkdir(parents=True, exist_ok=True)
        
        for gqi_file in gqi_files:
            fa_mapping_file = reg_dir / (gqi_file.name + ".dti_fa.nii.gz.to_mni.mz")
            
            if fa_mapping_file.exists():
                cmd = [
                    "/data/yijie/software/dsi-studio/dsi_studio",
                    "--action=reg",
                    "--source={}".format(gqi_file),
                    "--mapping={}".format(fa_mapping_file),
                    "--output={}".format(reg_dir / (gqi_file.name + ".mni.fz")),
                ]
                subprocess.run(cmd)
                

def run_tractography(subj_dir):
    transform_dir = subj_dir.glob("*/dwi/transform")
    dwi_dir = transform_dir.parent
    
    tractography_dir = dwi_dir / "tractography"
    tractography_dir.mkdir(parents=True, exist_ok=True)
    
    gqi_files = transform_dir.glob("*gqi.fz.mni.fz")
    
    for gqi_file in gqi_files:
        tract_file = tractography_dir / (gqi_file.name + ".tt.gz")
        
        if not tract_file.exists():
            cmd = [
                "/data/yijie/software/dsi-studio/dsi_studio",
                "--action=trk",
                "--source={}".format(gqi_file),
                "--method=0",
                "--seed_count=1000000",
                "--output={}".format(tract_file),
            ]
            subprocess.run(cmd)    


# test_dir = Path("/data/dataset/FiberDataHub/data-hcp/lifespan/hcp-ya/100206")
# export_dti_fa(test_dir)
# register_fa_to_mni(test_dir)
# register_gqi_to_mni(test_dir)

subject_dirs = []

for repo in root_dir.iterdir():
    if not repo.is_dir():
        continue
    
    for sub_tag in repo.iterdir():
        if not sub_tag.is_dir():
            continue
        
        for subj_dir in sub_tag.iterdir():
            if not subj_dir.is_dir():
                continue
            
            subject_dirs.append(subj_dir)
            
            
def pipeline(subj_dir):
    export_dti_fa(subj_dir)
    register_fa_to_mni(subj_dir)
    register_gqi_to_mni(subj_dir)
    # run_tractography(subj_dir)
    

tmp = Parallel(n_jobs=30)(delayed(pipeline)(subj_dir) for subj_dir in subject_dirs)

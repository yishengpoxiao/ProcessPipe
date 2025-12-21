import pathlib
import subprocess
import sys


refer_img = "/data/yijie/Tractography/resources/MNI_FA_template.nii.gz"


def export_dti_metric(gqi_file):
    gqi_dir = gqi_file.parent
    dwi_dir = gqi_dir.parent
    
    dti_dir = dwi_dir / "dti"
    dti_dir.mkdir(parents=True, exist_ok=True)
    
    exported_fa = dti_dir / (gqi_file.name + ".dti_fa.nii.gz")
    
    fa_file_orig = gqi_dir / (gqi_file.name + ".dti_fa.nii.gz")
    
    if not exported_fa.exists() and not fa_file_orig.exists():
        cmd = [
            "/data/yijie/software/dsi-studio/dsi_studio",
            "--action=exp",
            "--source={}".format(gqi_file),
            "--export=dti_fa",
        ]
        subprocess.run(cmd)
        
    if not exported_fa.exists() and fa_file_orig.exists():
        fa_file_orig.rename(exported_fa)
        

def run_tractography(gqi_file):
    gqi_dir = gqi_file.parent
    dwi_dir = gqi_dir.parent
    
    tractography_path = gqi_dir / gqi_file.name.replace('.gqi.fz', '.orig.tt.gz')
    
    if not tractography_path.exists():
        cmd = [
            "/data/yijie/software/dsi-studio/dsi_studio",
            "--action=trk",
            "--source={}".format(gqi_file),
            "--tract_count=150000",
            "--method=1",
            "--output={}".format(tractography_path),
        ]
        subprocess.run(cmd)


def register_to_mni(gqi_file):
    gqi_dir = gqi_file.parent
    dwi_dir = gqi_dir.parent
    
    dti_dir = dwi_dir / "dti"
    
    fa_file = dti_dir / (gqi_file.name + ".dti_fa.nii.gz")
    
    tractography_dir = dwi_dir / "tractography"
    tractography_dir.mkdir(parents=True, exist_ok=True)
    
    tractography_in_orig = gqi_dir / gqi_file.name.replace('.gqi.fz', '.orig.tt.gz')
    
    tractography_in_mni = tractography_dir / gqi_file.name.replace('.gqi.fz', '.mni.tt.gz')
    registered_tractography = dti_dir / (gqi_file.name.replace('.gqi.fz', '.orig.tt.gz.wp.tt.gz'))
    
    if not tractography_in_mni.exists() and not registered_tractography.exists():
        cmd = [
            "/data/yijie/software/dsi-studio/dsi_studio",
            "--action=reg",
            "--reg_type=0",
            "--source={}".format(fa_file),
            "--to={}".format(refer_img),
            "--s2t={}".format(tractography_in_orig),
            "--output={}".format(dti_dir),
        ]
        subprocess.run(cmd)
        
    if not tractography_in_mni.exists() and registered_tractography.exists():
        registered_tractography.rename(tractography_in_mni)


root_dir = pathlib.Path('/data/dataset/FiberDataHub/data-hcp/lifespan/hcp-ya/')
gqi_files = root_dir.glob('**/*.gqi.fz')
gqi_files = sorted(gqi_files)

train_dir = pathlib.Path('/data/yijie/TractographyTemplate/train_dir')
val_dir = pathlib.Path('/data/yijie/TractographyTemplate/val_dir')
test_dir = pathlib.Path('/data/yijie/TractographyTemplate/test_dir')

train_dir.mkdir(exist_ok=True)
val_dir.mkdir(exist_ok=True)
test_dir.mkdir(exist_ok=True)

for gqi_file in gqi_files[:80]:
    export_dti_metric(gqi_file)
    run_tractography(gqi_file)
    register_to_mni(gqi_file)
    
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '')
    
    tractography_in_mni = gqi_file.parent.parent / 'tractography' / gqi_file.name.replace('.gqi.fz', '.mni.tt.gz')
    
    soft_link_path = train_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_in_mni)
                
    
for gqi_file in gqi_files[80:90]:
    export_dti_metric(gqi_file)
    run_tractography(gqi_file)
    register_to_mni(gqi_file)
    
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '')
    
    tractography_in_mni = gqi_file.parent.parent / 'tractography' / gqi_file.name.replace('.gqi.fz', '.mni.tt.gz')
    
    soft_link_path = val_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_in_mni)

for gqi_file in gqi_files[90:100]:
    export_dti_metric(gqi_file)
    run_tractography(gqi_file)
    register_to_mni(gqi_file)
    
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '')
    
    tractography_in_mni = gqi_file.parent.parent / 'tractography' / gqi_file.name.replace('.gqi.fz', '.mni.tt.gz')
    
    soft_link_path = test_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_in_mni)

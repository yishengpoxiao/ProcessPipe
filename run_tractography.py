import pathlib
import subprocess
import sys


root_dir = pathlib.Path('/data/dataset/FiberDataHub/data-hcp/lifespan/hcp-ya/')
gqi_files = root_dir.glob('**/*gqi.fz.wp.fz')
gqi_files = sorted(gqi_files)

train_dir = pathlib.Path('/data/yijie/TractographyTemplate/train_dir')
val_dir = pathlib.Path('/data/yijie/TractographyTemplate/val_dir')
test_dir = pathlib.Path('/data/yijie/TractographyTemplate/test_dir')

train_dir.mkdir(exist_ok=True)
val_dir.mkdir(exist_ok=True)
test_dir.mkdir(exist_ok=True)

for gqi_file in gqi_files[:80]:
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '').replace('.wp', '')
    sub_dwi_dir = gqi_file.parent.parent
    tractography_dir = sub_dwi_dir / 'tractography'
    tractography_dir.mkdir(exist_ok=True)
    tractography_file = tractography_dir / f'{sub_id}.mni.tt.gz'
    
    command = ['/data/yijie/software/dsi-studio/dsi_studio', 
               '--action=trk',
               '--tract_count=100000',
               '--method=1',
                f'--source={str(gqi_file)}',
                f'--output={str(tractography_file)}',]
    subprocess.run(command)
    
    soft_link_path = train_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_file)
                
    
for gqi_file in gqi_files[80:90]:
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '').replace('.wp', '')
    sub_dwi_dir = gqi_file.parent.parent
    tractography_dir = sub_dwi_dir / 'tractography'
    tractography_dir.mkdir(exist_ok=True)
    tractography_file = tractography_dir / f'{sub_id}.mni.tt.gz'
    
    command = ['/data/yijie/software/dsi-studio/dsi_studio', 
               '--action=trk',
               '--tract_count=100000',
               '--method=1',
                f'--source={str(gqi_file)}',
                f'--output={str(tractography_file)}']
    subprocess.run(command)
    
    soft_link_path = val_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_file)

for gqi_file in gqi_files[90:100]:
    sub_id = gqi_file.name.replace('.gqi.fz', '').replace('.gqi', '').replace('.fz', '').replace('.wp', '')
    sub_dwi_dir = gqi_file.parent.parent
    tractography_dir = sub_dwi_dir / 'tractography'
    tractography_dir.mkdir(exist_ok=True)
    tractography_file = tractography_dir / f'{sub_id}.mni.tt.gz'
    
    command = ['/data/yijie/software/dsi-studio/dsi_studio', 
               '--action=trk',
               '--tract_count=100000',
               '--method=1',
                f'--source={str(gqi_file)}',
                f'--output={str(tractography_file)}',]
    subprocess.run(command)

    soft_link_path = test_dir / f'{sub_id}.mni.tt.gz'
    if not soft_link_path.exists():
        soft_link_path.symlink_to(tractography_file)

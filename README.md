# ProcessPipe

ProcessPipe 是一个面向脑影像数据处理的脚本集合，主要用于扩散磁共振成像（dMRI）和 T1 结构像的批量预处理、纤维追踪以及后续指标提取。仓库中的脚本以 Python 为入口，实际工作依赖 FreeSurfer、MRtrix3、3D Slicer、DSI Studio、WhiteMatterAnalysis 等外部软件完成。

当前仓库更像是一个实验室内部使用的流程脚本仓库，而不是一个可直接安装的 Python 包：多数脚本通过**硬编码路径**定位数据目录和外部软件，因此在正式运行前通常需要先根据本机环境修改脚本中的路径配置。

## 仓库主要用途

从脚本内容看，这个仓库主要覆盖以下处理阶段：

1. **DICOM 转 NIfTI**
2. **按 BIDS 风格重组数据目录**
3. **T1w 结构像预处理**
4. **dMRI 预处理**
5. **基于 UKF / DSI Studio 的纤维追踪**
6. **白质束测量、DTI 标量和解剖指标提取**

## 目录说明

### 根目录主要脚本

| 脚本 | 作用 |
| --- | --- |
| `s0_dicom_to_nifti.py` | 批量解压受试者 zip 数据，调用 `dcm2niix` 转换为 NIfTI，并根据 JSON 中的 `BidsGuess` 信息重命名到 `anat` / `dwi` 等目录。 |
| `s1_1_preprocess_T1w.py` | 遍历受试者的 `anat` 目录，查找 `*_T1w.nii.gz`，调用 FreeSurfer `recon-all` 做 T1 结构像处理。 |
| `s1_2_preprocess_dMRI.py` | dMRI 主预处理脚本。包括梯度检查、MRtrix 预处理、bias correction、NIfTI/NRRD 转换、CNN 脑掩膜、UKF tractography 和 WMA atlas 应用。 |
| `process_dmri.py` | 另一套 dMRI 处理脚本，流程偏向 NRRD 转换、DTIPrep 质控、CNN masking、UKF tractography 与 WMA。 |
| `run_tractography_in_mni.py` | 面向 `.gqi.fz` 数据，调用 DSI Studio 导出 DTI FA、执行 tractography、配准到 MNI，并整理训练/验证/测试集软链接。 |

### 子目录

| 目录 | 说明 |
| --- | --- |
| `BIDS_organize/` | 数据整理相关脚本，例如 DICOM 转 NIfTI、按 BIDS 风格组织结构。 |
| `Preprocess/` | 预处理脚本，包含基于 MRtrix 的处理流程。 |
| `analysis_pipe/` | 后处理与分析脚本，如 DTI 标量计算、白质束测量、体积指标和 glymphatic 相关指标提取。 |

## 典型流程

从入口脚本命名和处理逻辑来看，一个常见处理顺序大致如下：

1. 运行 `s0_dicom_to_nifti.py`  
   - 解压原始数据
   - 调用 `dcm2niix` 转换
   - 根据 `BidsGuess` 重命名并放入目标目录

2. 运行 `s1_1_preprocess_T1w.py`  
   - 对 `anat/*_T1w.nii.gz` 执行 FreeSurfer `recon-all`

3. 运行 `s1_2_preprocess_dMRI.py` 或 `process_dmri.py`  
   - 进行 dMRI 预处理
   - 生成脑掩膜
   - 执行纤维追踪
   - 输出 WMA 相关测量结果

4. 按需运行 `analysis_pipe/` 中的脚本  
   - 提取 DTI、体积或其他衍生指标

## 预期数据组织方式

多个脚本默认假设数据按“站点 / 受试者”层级组织，例如：

```text
/path/to/data_root/
└── site_name/
    └── subject_id/
        ├── anat/
        │   └── subject_id_T1w.nii.gz
        ├── dwi/
        │   ├── subject_id_PA_run-01_dwi.nii.gz
        │   ├── subject_id_PA_run-01_dwi.bval
        │   ├── subject_id_PA_run-01_dwi.bvec
        │   └── ...
        └── subject.zip
```

不同脚本中使用的数据根目录并不完全一致：

- `s0_dicom_to_nifti.py`、`s1_1_preprocess_T1w.py`、`s1_2_preprocess_dMRI.py`、`process_dmri.py` 这类脚本主要面向“站点 / 受试者”目录；
- `run_tractography_in_mni.py` 则面向包含 `.gqi.fz` 文件的数据集目录。

因此运行前请先检查每个脚本顶部的 `input_dir`、参考模板路径和软件安装路径，并改成适合当前环境的绝对路径。

## 外部依赖

脚本中直接调用了大量命令行工具，常见依赖包括：

- Python 3
- `nibabel`
- `simplejson`
- `numpy` / `scipy`（部分脚本）
- `joblib`（部分脚本）
- `dcm2niix`
- FreeSurfer
- MRtrix3（如 `mrconvert`、`dwidenoise`、`dwifslpreproc`、`dwibiascorrect`、`dwigradcheck`）
- 3D Slicer 及其 DWI/UKF 相关模块
- CNN-Diffusion-MRIBrain-Segmentation
- WhiteMatterAnalysis
- DSI Studio
- ANTs
- DTIPrep（部分流程）

## 使用方式

仓库没有统一的命令行入口，也没有打包配置。通常是直接运行某个脚本：

```bash
python s0_dicom_to_nifti.py
python s1_1_preprocess_T1w.py
python s1_2_preprocess_dMRI.py
python process_dmri.py
```

大多数脚本会：

- 自动遍历 `input_dir` 下的全部站点和受试者
- 使用 `multiprocessing.Pool` 并行处理
- 把中间结果和输出写回受试者目录内部

## 主要输出示例

根据脚本内容，常见输出包括：

- `anat/<subject>/` 下的 FreeSurfer 结果
- `dwi/processed/` 下的预处理 dMRI、`.bval`、`.bvec`、`.nrrd`
- `dwi/tractography/<subject>.vtk` 纤维追踪结果
- `dwi/WMA/<subject>/AnatomicalTracts/diffusion_measurements_anatomical_tracts.csv`
- `dti/` 目录下的 DTI FA 及配准到 MNI 的结果

## 运行前注意事项

1. **先改路径**：脚本中大量路径写死在文件顶部，迁移环境时必须先调整。  
2. **确认软件环境**：部分脚本依赖 conda 环境、Slicer 扩展、FreeSurfer 初始化脚本等。  
3. **确认数据命名**：某些逻辑依赖文件名里是否包含 `PA_`、`AP_`、`_T1w`、`_dwi` 等关键字。  
4. **资源占用较高**：脚本中常直接使用 `64`、`80`、`90` 线程，运行前建议按服务器资源修改。  
5. **建议先小规模测试**：先挑选少量受试者验证路径、权限和软件调用是否正常，再批量运行。  

## 测试与构建说明

当前仓库中未发现：

- `README` 以外的项目文档
- `requirements.txt` / `pyproject.toml` / `setup.py`
- 自动化测试配置
- lint 或 build 配置

因此这个仓库目前主要通过直接运行脚本进行验证，而不是通过统一的测试框架或打包流程进行管理。

# ProcessPipe

`ProcessPipe` 是一组用于扩散磁共振成像（dMRI）数据整理、预处理、纤维追踪和数据集构建的 Python 脚本。脚本面向本地数据目录与既有软件环境运行，主要覆盖 DICOM/NIfTI 转换、BIDS 风格整理、dMRI/T1w 预处理、DSI Studio/MRtrix 纤维追踪及训练集准备。

> 注意：多数脚本内含数据目录、软件路径、线程数和输出目录。运行前请先检查并按实际环境修改这些配置；部分脚本会移动或删除数据文件，建议先在副本上验证。

## 目录结构与运行方式

实际实现已按职责移入 `processpipe/`：

- `processpipe/core/`：外部命令、BIDS 文件名、sidecar 与相位方向等公共工具。
- `processpipe/workflows/`：BIDS 整理、DSI/MRtrix 基准追踪、T1w/FreeSurfer 与 UKF/WMA 预处理流程。
- `processpipe/tractography/`：MNI 追踪、纤维下采样和训练/验证/测试集切分。
- 根目录脚本、`BIDS_organize/` 以及 `Preprocess/` 中的同名脚本均为兼容入口，原有调用路径仍可使用。

推荐从项目根目录使用统一命令：

```bash
python -m processpipe benchmark --profile adni --dry-run
python -m processpipe bids-rename --help
python -m processpipe dsi-mni --input-dir /path/to/subjects
python -m processpipe tract-mni --dry-run
```

每个可运行流程均支持 `--help`；会修改数据或调用外部影像软件的流程提供 `--dry-run` 时，会仅列出计划处理的对象。

## 功能分类

### 1. DICOM 转换与 BIDS 整理

| 脚本 | 功能 |
| --- | --- |
| `processpipe.workflows.bids_organize` | 统一实现以下 BIDS/DICOM 流程；`s0_dicom_to_nifti.py` 和 `BIDS_organize/` 内同名脚本继续作为兼容入口。 |
| `bids-asd` | 解压受试者 DICOM 压缩包，调用 `dcm2niix` 转换为 NIfTI，并依据 JSON 中的 `BidsGuess` 将结果归入相应模态目录。 |
| `bids-abvib-convert` | 将按检查日期组织的 DICOM 数据批量转换为按 session 划分的 NIfTI 数据。 |
| `bids-rename` | 根据 `BidsGuess` 重命名 DWI 文件及其 `.bval`、`.bvec`、`.json` sidecar。 |
| `bids-reorganize` | 保留有效 DWI/相位编码数据，删除不需要的序列，并将 NIfTI 与 sidecar 移入 `dwi/` 目录。 |
| `bids-dsi-output` | 将 DSI Studio 输出整理到 `subject/session/dwi/gqi` 层级。 |

### 2. 影像预处理

| 脚本 | 功能 |
| --- | --- |
| `dsi-mni`（`Preprocess/preprocess.py`） | 主 dMRI 预处理流程：梯度检查、DSI Studio EDDY/TOPUP 处理、脑掩膜、DTI 拟合、MNI 配准、bvec 旋转和 GQI 重建。支持有或无 session 的受试者目录。 |
| `t1w`（`s1_1_preprocess_T1w.py`） | 查找 T1w 图像并批量调用 FreeSurfer `recon-all`。 |
| `ukf-wma`（`s1_2_preprocess_dMRI.py`） | MRtrix/UKF/WMA 工作流：降噪、畸变/偏置校正、NRRD 转换、脑掩膜、UKF 追踪和 ORG atlas 测量。 |

### 3. 多数据集纤维追踪基准处理

这些脚本针对不同数据集目录布局运行相同类型的 MRtrix 与 DSI Studio 处理：梯度检查、响应函数/FOD 估计、三次 iFOD2 追踪、GQI 重建、三次 DSI Studio 追踪，以及 VTK 转换。

| 脚本 | 数据集/目录布局 |
| --- | --- |
| `benchmark --profile adni`（`ADNI_process.py`） | ADNI 受试者目录布局。 |
| `benchmark --profile ppmi`（`PPMI_process.py`） | PPMI 受试者目录布局。 |
| `benchmark --profile cnp`（`CNP_process.py`） | CNP 的 site/type/subject 嵌套目录布局。 |
| `benchmark --profile abideii`（`ABIDEII_process.py`） | ABIDE II 的站点和 QC 后 DWI 文件布局。 |

输出按 iFOD2 与 DSI Studio 的三次重复结果分别存放，以便评估追踪随机性的影响。

### 4. 纤维文件与训练集工具

| 脚本 | 功能 |
| --- | --- |
| `tract-mni`（`run_tractography_in_mni.py`） | 从 GQI 文件导出 DTI 指标，执行 DSI Studio 追踪并配准到 MNI 空间，再按训练/验证/测试范围创建软链接。 |
| `tract-downsample`（`downsample_vtk_in_pro.py`） | 按纤维所在目录去重后，批量调用 White Matter Analysis 下采样 VTK/VTP 文件。 |
| `tract-split`（`e.py`） | 将已下采样的 UKF 纤维文件按固定范围软链接到训练、验证和测试目录。 |

## 主要外部依赖

- Python：`numpy`、`nibabel`、`joblib`
- DICOM 转换：`dcm2niix`
- MRtrix3：`mrconvert`、`dwigradcheck`、`dwi2response`、`dwi2fod`、`tckgen` 等
- DSI Studio
- FSL：`dtifit`
- ANTs：配准与变换工具
- FreeSurfer：`recon-all`
- 3D Slicer / SlicerDMRI、UKFTractography
- White Matter Analysis / ORG Atlas

## 数据与运行注意事项

- DWI 文件必须与对应的 `.bval`、`.bvec` 文件匹配；涉及 BIDS 整理的流程还会使用 `.json` sidecar。
- `reorganize_structure.py` 会删除未保留的 NIfTI 及其 sidecar；使用前务必确认筛选规则。
- 多数流程通过“输出文件是否存在”判断是否跳过步骤。删除中间产物后再次运行可能触发重新处理。
- 并行数和工具线程数在各脚本中单独设置，应根据机器资源调整，避免多个任务同时占满 CPU 或内存。
- 远程同步功能已移除；仓库不再包含通过 SSH/SCP 复制数据的脚本。

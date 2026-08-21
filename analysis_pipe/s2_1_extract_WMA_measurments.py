#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import glob
import os

import numpy as np
import pandas



def main():
    # inputfolder1 = '/data04/ASD_Li_lab/2B_pre/HC_Time2'
    inputfolder1 = '/data04/ASD_Li_lab/TD_Time1'
    inputfolder2 = '/data04/ASD_Li_lab/2B_pre/TD_Time1_1'
    appenedmeasurefile = '/data04/ASD_Li_lab/results/TD_Time1_appended_measure.csv'

    subject_folders = []
    for sub_id in os.listdir(inputfolder1):
        if not os.path.isdir(os.path.join(inputfolder1, sub_id)):
            continue

        subject_folders.append(os.path.join(inputfolder1, sub_id))

    for sub_id in os.listdir(inputfolder2):
        if not os.path.isdir(os.path.join(inputfolder2, sub_id)):
            continue

        subject_folders.append(os.path.join(inputfolder2, sub_id))

    subject_folders = sorted(subject_folders)
    print(subject_folders)

    subject_IDs = [os.path.basename(folder) for folder in subject_folders]

    # print()
    # print(f'Subject IDs: (n={len(subject_IDs)}): ')
    # print(subject_IDs)

    # anatomical tracts
    stats = pandas.read_table(os.path.join(subject_folders[0], f'dwi/WMA/{subject_IDs[0]}/AnatomicalTracts/diffusion_measurements_anatomical_tracts.csv'), delimiter=' , ', engine='python')

    fields = [col.strip() for col in stats.columns]
    fields = fields[1:]
    # print()
    # print(f'Tract diffusion measures per subject: (n={len(fields)}): ')
    # print(fields)

    tracts = stats.to_numpy()[:, 0]
    tracts = [os.path.basename(filepath).replace('.vtp', '').replace('.vtk', '').strip() for filepath in tracts]
    # print()
    # print(f'White matter tracts per subject: (n={len(tracts)}): ')
    # print(tracts)

    appended_fields = ['subjectkey']
    for tract in tracts:
        for field in fields:
            appended_fields.append(f"{tract}.{field}")

    # print()
    # print(f'Appended tract diffusion measure fields per subject: (n={len(appended_fields)}): ')
    # print(appended_fields[:10], ' ... ')

    data = []
    for s_idx, subject_folder in enumerate(subject_folders):
        print(' * loading tract feature for subject #%04d (subject ID - %s):' %(s_idx, subject_IDs[s_idx]))
        csv = os.path.join(subject_folder, f'dwi/WMA/{subject_IDs[s_idx]}/AnatomicalTracts/diffusion_measurements_anatomical_tracts.csv')
        stats = pandas.read_table(csv, delimiter=' , ', engine='python')

        stats_data = stats.to_numpy()[:, 1:]
        stats_data_vec = stats_data.flatten()
        # print(len(appended_fields))
        # print(stats_data_vec.shape)
        if stats_data_vec.shape[0] != len(appended_fields) - 1:
            print("Error: Check if the diffusion measure file has the same rows and columns with other subjects!")
            exit()

        data.append(stats_data_vec)

    data = np.array(data)
    data = np.concatenate([np.array(subject_IDs)[:, np.newaxis], data], axis = 1)

    df = pandas.DataFrame(data, columns=appended_fields)

    # print()
    # print('Appended tract diffusion measures:')
    # print(df)

    df.to_csv(os.path.abspath(appenedmeasurefile).replace('.csv', '_anatomical_tracts.csv'), index=False)
    # print()
    # print('Output file at:', os.path.abspath(appenedmeasurefile).replace('.csv', '_anatomical_tracts.csv'))


if __name__ == "__main__":
    main()
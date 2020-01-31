#!/usr//bin/env python3

# T. Vuillaume, 12/09/2019
# merge and copy DL1 data after production
# Modifications by E. Garcia, 21/01/2020


# 1. check job_logs
# 2. check that all files have been created in DL1 based on training and testing lists
# 3. move DL1 files in final place
# 4. merge DL1 files
# 5. move running_dir 

import argparse
from .data_management import *
# from lstchain.io import smart_merge_h5files

parser = argparse.ArgumentParser(description="Merge and copy DL1 data after production. \n"
                                             " 1. check job_logs \n"
                                             " 2. check that all files have been created in DL1 based on training "
                                             "and testing lists \n"
                                             " 3. move DL1 files in final place \n"
                                             " 4. merge DL1 files \n"
                                             " 5. move running_dir ")

parser.add_argument('input_dir', type=str,
                    help='path to the DL1 files directory to merge, copy and move',
                    )

parser.add_argument('--flag_workflow_mode', '-flag', type=str,
                    dest='flag_workflow_mode',
                    help='Flag to indicate if the code is run within the r0_to_dl2 full workflow, and thus some '
                         'arguments must be returned for the following steps.',
                    default=False
                    )


def check_files_in_dir_from_file(directory, file):
    """
    Check that a list of files from a file exist in a dir

    Parameters
    ----------
    directory
    file

    Returns
    -------

    """
    with open(file) as f:
        lines = f.readlines()

    files_in_dir = os.listdir(directory)
    files_not_in_dir = []
    for line in lines:
        filename = os.path.basename(line.rstrip('\n'))
        if filename not in files_in_dir:
            files_not_in_dir.append(filename)

    return files_not_in_dir


def readlines(file):
    with open(file) as f:
        lines = [line.rstrip('\n') for line in f]
    return lines


def move_dir_content(src, dest):
    files = os.listdir(src)
    for f in files:
        shutil.move(os.path.join(src, f), dest)
    os.rmdir(src)


def main(input_dir, flag_full_workflow=False, particle2jobs_dict={}, particle=None):

    if flag_full_workflow:
        log_merge = {particle: {}}
        log_merge[particle]['logs_script_test'] = []
        log_merge[particle]['logs_script_train'] = []

        wait_jobs = ','.join(map(str, particle2jobs_dict[particle].keys()))

    print("\n ==== START {} ==== \n".format(sys.argv[0]))

    JOB_LOGS = os.path.join(input_dir, 'job_logs')
    training_filelist = os.path.join(input_dir, 'training.list')
    testing_filelist = os.path.join(input_dir, 'testing.list')
    running_DL1_dir = os.path.join(input_dir, 'DL1')
    DL1_training_dir = os.path.join(running_DL1_dir, 'training')
    DL1_testing_dir = os.path.join(running_DL1_dir, 'testing')
    final_DL1_dir = input_dir.replace('running_analysis', 'DL1')
    logs_destination_dir = input_dir.replace('running_analysis', 'analysis_logs')

    # 1. check job logs
    check_job_logs(JOB_LOGS)

    # 2. check that all files have been created in DL1 based on training and testing lists
    # just check number of files first:
    if not len(os.listdir(DL1_training_dir)) == len(readlines(training_filelist)):
        tf = check_files_in_dir_from_file(DL1_training_dir, training_filelist)
        if tf != [] and not flag_full_workflow:
            query_continue("{} files from the training list are not in the `DL1/training` directory:\n{} "
                           "Continue ?".format(len(tf), tf))
        elif tf != [] and flag_full_workflow:
            to_log = "\t{} files from the training list are not in the `DL1/training` directory:\n{} " \
                     "\tCannot stop workflow. CHECK LATER !".format(len(tf), tf)
            log_merge[particle]['logs_script_train'].append(to_log)

    if not len(os.listdir(DL1_testing_dir)) == len(readlines(testing_filelist)):
        tf = check_files_in_dir_from_file(DL1_testing_dir, testing_filelist)
        if tf != [] and not flag_full_workflow:
            query_continue("{} files from the testing list are not in the `DL1/testing directory:\n{} "
                           "Continue ?".format(len(tf), tf))
        elif tf != [] and flag_full_workflow:
            to_log = "\t{} files from the testing list are not in the `DL1/testing directory:\n{} " \
                     "\tCannot stop workflow. CHECK LATER !".format(len(tf), tf)
            log_merge[particle]['logs_script_test'].append(to_log)

    # 3. merge DL1 files
    print("\tmerging starts")
    for set_type in ['testing', 'training']:
        tdir = os.path.join(running_DL1_dir, set_type)
        output_filename = 'dl1_'
        for i in [-4, -3, -2, -1]:
            output_filename += running_DL1_dir.split('/')[i]
            output_filename += '_'
        output_filename += set_type
        output_filename += '.h5'
        output_filename = os.path.join(running_DL1_dir, output_filename)
        print(f"\t\tmerge output: {output_filename}")

    # 3.1 sbatch the jobs (or send them interactively depending) if the script is(not) run as part of the whole workflow
        filelist = [os.path.join(tdir, f) for f in os.listdir(tdir)]
        if not flag_full_workflow:
            cmd = f"lstchain_merge_hdf5_files -d {tdir} -o {output_filename}"
            os.system(cmd)
            # smart_merge_h5files(filelist, output_filename)
        else:
            cmd = f"sbatch --parsable --dependency=afterok:{wait_jobs} " \
                  f"--wrap='lstchain_merge_hdf5_files -d {tdir} -o {output_filename}'"
            jobid = os.popen(cmd).read().split('\n')
            log_merge[particle][jobid] = cmd

            # print(f'\t\t{cmd}')
            print(f'\t\tSubmitted batch job {jobid}')

    # 4. move DL1 files in final place
    check_and_make_dir(final_DL1_dir)
    move_dir_content(running_DL1_dir, final_DL1_dir)
    print("\tDL1 files have been moved to {}".format(final_DL1_dir))

    # copy lstchain config file there too
    config_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.json')]
    for file in config_files:
        shutil.copyfile(file, os.path.join(final_DL1_dir, os.path.basename(file)))

    # 5. move running_dir as logs
    check_and_make_dir(logs_destination_dir)
    move_dir_content(input_dir, logs_destination_dir)
    print("\tLOGS have been moved to {}".format(logs_destination_dir))

    print("\n ==== END {} ==== \n".format(sys.argv[0]))

    if flag_full_workflow:
        return log_merge, jobid


if __name__ == '__main__':
    args = parser.parse_args()
    main(args.input_dir, args.flag_workflow_mode)

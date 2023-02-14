#!/usr/bin/env bash

while getopts v: flag
do
    case "${flag}" in
        v) version=${OPTARG};;
    esac
done

echo "Testing version $version"

source /opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh
conda activate blender

mkdir -p /Users/ole/Documents/HumGen3D/tests/output
blender_versions=("2.93.11" "3.1.2" "3.2.2" "3.3.0") # "3.0.1" "3.3.1"
for blender_version in "${blender_versions[@]}"; do
    if [[ $blender_version != $version* ]]; then
        continue
    fi
    echo "Testing Blender $blender_version"
    exec_folder="/Users/ole/blender_executables"
    blender_executable=$(find $exec_folder -name "blender-$blender_version*")
    # If not, download it
    if [ -z "$blender_executable" ]; then
        blender-downloader $blender_version -d $exec_folder -r -e
        blender_executable=$(find $exec_folder -name "blender-$blender_version*")
    fi
    echo $blender_executable
    blender_executable="$blender_executable/Contents/MacOS/blender"
    echo $blender_executable
    # Run tests
    $blender_executable -b -P tests/prepare_blender_for_tests.py | grep -v 'already satisfied'
    LOG_FILE="/Users/ole/Documents/HumGen3D/tests/output/test_output_$blender_version.log"
    # exec 3>&1 1>>${LOG_FILE} 2>&1
    echo "STARTING TESTS FOR BLENDER $blender_version"
    echo "Starting time is $(date)" > $LOG_FILE
    if [ "$lf_flag" = 'true' ]; then
        python -m pytest ./tests/human/ --blender-executable $blender_executable --lf >> $LOG_FILE
    else
        python -m pytest ./tests/human/ --blender-executable $blender_executable >> $LOG_FILE
    fi
    echo "Wrote log to $LOG_FILE"
done
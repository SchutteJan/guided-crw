#!/bin/bash


find ../../datasets/jhmbd/Rename_Images/ -mindepth 2 -type d | grep -v .AppleDouble > eval/jhmdb_imglist.txt
find ../../datasets/jhmbd/joint_positions | grep -v .AppleDouble | grep mat > eval/jhmdb_lbllist.txt

cd eval
python3 gen_jhmbd.py > jhmdb_vallist.txt

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
from pathlib import Path

import lxml.etree
import mutagen
from mutagen.id3 import APIC, CHAP, CTOC, ID3, TIT2, TRCK, CTOCFlags


class OverDrive(object):

    exts = ['.mp3']

    def __init__(self, dirpath, title=None):
        self.dirpath = Path(dirpath)
        self.title = self.dirpath.name if title is None else title

        dirrst = '{title} Chapters'.format(title=self.title)
        self.dirrst = self.dirpath.parent.joinpath(dirrst)
        self.dirrst.mkdir(parents=True, exist_ok=True)

    def find_chapters(self):
        '''Find chapter from audio file in directory.'''
        def convert_duration(duration):
            value = int(duration * 1000)
            return value

        filepath = self.dirrst.joinpath('chapter.info')
        lst_chap = self.__find_chaps_dir()

        content = ''
        for chap in lst_chap:
            chap.update({'start': convert_duration(chap['start'])})
            content += '{start:12}\t{name}\n'.format(**chap)

        with open(filepath, 'w') as fp:
            fp.write(content)

    def split_chapters(self):
        '''Cut book into chapters.'''
        chapters = self.__load_chapters()

        # Clean result folder
        for filepath in self.__find_files(self.dirrst):
            Path(filepath).unlink()

        # Copy cover
        cover_name = '{title}-Cover.jpg'.format(title=self.title)
        src = Path(self.dirpath).joinpath(cover_name)
        cover = Path(self.dirrst).joinpath(cover_name)
        if Path(src).exists():
            shutil.copy(src, cover)

        audio = self.__merge_audios()
        length = mutagen.File(audio).info.length

        index_str = '0{0}'.format(len(str(len(chapters))))

        # Update chapter info and chapter
        ad = ID3(audio)
        lst_id = []
        for index in range(len(chapters)):
            index_chap = format(index+1, index_str)
            chap = chapters[index]

            start_next = length
            if index < len(chapters) - 1:
                start_next = chapters[index+1]['start']

            chapters[index]['duration'] = start_next - chap['start']

            # Add chapter
            cid = 'c{0}'.format(index_chap)
            ad.add(
                CHAP(element_id=cid, start_time=int(chap['start']*1000), end_time=int(start_next*1000),
                     sub_frames=[
                         TIT2(text=[chap['name']]),
                ]))

            lst_id.append(cid)

        else:
            # Add toc
            ad.add(
                CTOC(element_id=u"toc", flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
                     child_element_ids=lst_id,
                     sub_frames=[
                         TIT2(text=[self.title]),
                     ]))

            ad.save()

        # Cut audio
        index = 0
        ext = Path(audio).suffix
        for chap in chapters:
            index += 1
            index_chap = format(index, index_str)
            filepath = '{0} {1}{2}'.format(self.title, index_chap, ext)
            filepath = self.dirrst.joinpath(filepath)

            # Cut chapter
            self.__cut_audio(audio, chap['start'], chap['duration'], filepath)

            # Update meta data
            meta = {'title': chap['name'], 'track': index_chap}
            self.__update_meta(filepath, meta, cover)

        # Remove file
        Path(audio).unlink()

    def __load_chapters(self):
        '''Load chapter data from json.'''
        filepath = self.dirrst.joinpath('chapter.info')

        with open(filepath) as fp:
            lines = fp.readlines()

        lst_chap = []
        for line in lines:
            if '\t' not in line:
                continue
            lst = line.split('\t')
            lst_chap.append({
                'start': float(int(lst[0])/1000),
                'name': '\t'.join(lst[1:])
            })

        return lst_chap

    def __cut_audio(self, origin, start, duration, output):
        '''Cut audio from book.'''
        command = 'ffmpeg -y -i "{0}" -ss {1} -t {2} -acodec copy "{3}"'
        command = command.format(origin, start, duration, output)
        os.system(command)

    def __merge_audios(self):
        '''Merge audios into one.'''
        lst_file = self.__find_files(self.dirpath)

        audio = '{0}{1}'.format(self.title, Path(lst_file[0]).suffix)
        audio = self.dirrst.joinpath(audio)
        audio = '{0}'.format(str(audio))

        concat = 'concat:{0}'.format('|'.join(lst_file))

        command = 'ffmpeg -y -i "{0}" -acodec copy "{1}"'.format(concat, audio)
        os.system(command)

        # Update meta data
        self.__update_meta(audio, {'title': self.title})

        return audio

    def __find_chaps_file(self, filepath):
        '''Get chapters info base on OverDrive tag.'''
        audio = mutagen.File(filepath)
        tag = 'TXXX:OverDrive MediaMarkers'
        lst = audio.tags.getall(tag)

        # Check meta data
        if len(lst) != 1 or len(lst[0].text) != 1:
            raise Exception('Unable to get metadata of tag %s' % tag)

        text = lst[0].text[0]
        root = lxml.etree.fromstring(text)

        # Get list of chapter from xml
        rst = [{t.tag: t.text for t in maker.getchildren()}
               for maker in root.getchildren()]

        return rst, audio.info.length

    def __find_chaps_dir(self):
        '''Find all chaps from input directory'''
        lst_file = self.__find_files(self.dirpath)
        lst_chap = []
        offset = 0
        for filepath in lst_file:
            lst, length = self.__find_chaps_file(filepath)
            for marker in lst:
                start = self.__stamp_to_duration(marker['Time']) + offset
                chap = {
                    'start': start,
                    'name': marker['Name']
                }
                lst_chap.extend([chap])

            # Update offset
            offset += length

        return lst_chap

    def __stamp_to_duration(self, timestamp):
        '''Convert timestamp to duration.'''
        lst = timestamp.split(':')
        lst.reverse()

        duration = 0
        for i in range(len(lst)):
            duration += float(lst[i]) * (60 ** i)

        return duration

    def __find_files(self, dirpath):
        '''Find audio files in directory.'''
        lst = [str(f.absolute()) for f in dirpath.iterdir()
               if f.is_file() and f.suffix in self.exts]

        lst.sort()

        return lst

    def __update_meta(self, filepath, data, cover=None):
        '''Update meta data of audio file.'''
        info = {
            'title': TIT2,
            'track': TRCK
        }

        audio = ID3(filepath)
        for tag, text in data.items():
            clsn = info.get(tag)
            audio.add(clsn(encoding=3, text=str(text)))

        # Add cover
        if cover:
            audio.add(APIC(mime='image/jpeg', type=3, desc=u'Cover',
                  data=open(cover, 'rb').read()))

        audio.save(filepath)


parser = argparse.ArgumentParser(description='OverDrive tools')
parser.add_argument('action', metavar='action',
                    choices=['info', 'chapter'], default=None,
                    help='info | split')
parser.add_argument('book', metavar='book', help='Book directory')

args = parser.parse_args()

if __name__ == "__main__":

    dirpath = Path(args.book).absolute()
    action = args.action

    book = OverDrive(dirpath)

    if action == 'info':
        book.find_chapters()

    elif action == 'chapter':
        book.split_chapters()

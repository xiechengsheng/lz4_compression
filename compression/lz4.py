# -*- coding:utf8 -*-
"""
Usage:
    xlz4.py -c <dir_name.lz4r> <dir_name>
    xlz4.py -x <dir_name.lz4r> [<dir_name>]
    xlz4.py -l <dir_name.lz4r>
"""
# pep8


import os
import json
import sys

reload(sys)
sys.setdefaultencoding('utf8')
import base64

WINPLAT = ('win' in sys.platform)
SEP = '/'

a2b_hex = base64.binascii.a2b_hex
hexlify = base64.binascii.hexlify
unify_dir = lambda x: x.replace('\\', '/')


class Lz4Container(object):
    def __init__(self, ctype, **kwargs):
        # raise error if open in wrong mode
        if ctype not in ('c', 'x', 'l'):
            raise ValueError("Invalid mode ('%s')" % ctype)

        self.ctype = ctype
        self.kwargs = kwargs
        self.ok = False  # use for api

    # python lz4.py -c dir_name.lz4r dir_name 压缩指令
    def compress(self, blk_size=64):

        if self.ctype != 'c':
            raise IOError('File not open for compress')

        # 判断需要压缩的文件是否存在，是文件还是文件夹
        dir_name = self.kwargs.get('dir_name')
        self.type_of_dir_name = None
        if (dir_name and os.path.isdir(dir_name)):
            self.type_of_dir_name = 'dir'
        elif (dir_name and os.path.isfile(dir_name)):
            self.type_of_dir_name = 'file'
        if not self.type_of_dir_name:
            raise IOError("No such file or directory: '%s'" % dir_name)

        # 生成压缩文件路径和压缩文件名.lz4r
        dir_name = unify_dir(dir_name)
        base_dir_name = os.path.basename(dir_name.rstrip(SEP))
        file_name = self.kwargs.get('file_name', base_dir_name)
        if not file_name.endswith('.lz4r'):
            file_name = file_name + '.lz4r'
        full_file_name = os.path.abspath(file_name)
        full_file_dir = os.path.dirname(full_file_name)
        os.makedirs(full_file_dir) if not os.path.isdir(full_file_dir) \
            else None

        # 存在同名文件直接删除之前的文件
        if os.path.isfile(full_file_name):
            os.remove(full_file_name)
        # get dir_name index in case of long dir_name
        base_dir_name_index = len(dir_name.rstrip(SEP).split(SEP)) - 1
        # 存储
        outfile = open(full_file_name, 'wb')
        if self.type_of_dir_name == 'dir':
            # 使用lz4算法压缩所有文件和文件夹
            # 遍历所有文件夹与文件，并通过数据块的形式写入目的压缩文件
            for parent, dirnames, infile_names in os.walk(dir_name):
                #
                parent = unify_dir(parent)
                header_dir = SEP.join(parent.split(SEP)[base_dir_name_index:])
                for infile_name in infile_names:

                    infile_name = infile_name.decode('gbk')
                    parent = parent.decode('gbk')
                    full_infile_name = os.path.join(parent, infile_name)
                    infile = open(full_infile_name, 'rb')
                    blk_count = 0
                    while True:
                        blk = infile.read(blk_size * (2 ** 10))
                        if not blk:
                            break

                        # header for blk:
                        header = [(header_dir if blk_count == 0 else None),
                                  (infile_name if blk_count == 0 else None),
                                  blk_count,  # is new file or not
                                  len(blk)]  # bytes
                        blk_count += 1
                        b64str = base64.encodestring(json.dumps(header))
                        outfile.write(hexlify(b64str))
                        outfile.write('\n')
                        outfile.write(blk)
                        del blk
                    infile.close()

        # 需要压缩的直接是文件
        # 统计文件块大小，压缩
        elif self.type_of_dir_name == 'file':
            # split file
            infile = open(dir_name, 'rb')
            blk_count = 0  # block count
            while True:
                blk = infile.read(blk_size * (2 ** 10))
                if not blk:  # end if down
                    break

                # header for blk info
                header = [('./' if blk_count == 0 else None),
                          (os.path.basename(dir_name) if blk_count == 0 else
                           None),
                          blk_count,  # is new file or not
                          len(blk)]  # bytes
                blk_count += 1
                b64str = base64.encodestring(json.dumps(header))
                outfile.write(hexlify(b64str))
                outfile.write('\n')
                outfile.write(blk)
                del blk
            infile.close()
        outfile.flush()
        outfile.close()
        self.ok = True

    # python lz4.py -x <dir_name.lz4r> [<dir_name>]
    # python lz4.py -l <dir_name.lz4r>
    def decompress(self):

        # raise error for wrong mode
        if self.ctype not in ('x', 'l'):
            raise IOError('File not open for decompress')

        # 文件不存在处理异常
        file_name = self.kwargs.get('file_name')
        if not (file_name and os.path.isfile(file_name)):
            raise IOError("No such file or directory: '%s'" % file_name)

        replcae_dir_name = self.kwargs.get('dir_name')

        # decompress
        infile = open(file_name, 'rb')
        outfile_name = None
        while True:
            header = infile.readline()  # file header
            if not header:
                break
            # decode header
            try:
                raw_json = base64.decodestring(a2b_hex(header.strip()))
                header = json.loads(raw_json)
            except TypeError as e:
                raise TypeError("'%s' is not lz4r_type file" % file_name)

            # header列表中存储有lz4r块大小信息
            blk_count = header[2]

            # print list
            # header[1] 存储有文件名信息
            if self.ctype == 'l':
                if (blk_count == 0):
                    print(header[1])
                infile.seek(header[-1], 1)
                continue

            # header[0]: dir of origin file
            file_dir = header[0]
            if (blk_count == 0):  # means new file
                # 把原来文件名改成需要解压的文件名
                if replcae_dir_name and file_dir:
                    drive, sub_dir = os.path.splitdrive(file_dir)
                    if sub_dir:
                        split_sub_dir = unify_dir(sub_dir).split(SEP)
                        if split_sub_dir and len(split_sub_dir) > 0:
                            split_sub_dir[0] = unify_dir(replcae_dir_name)
                        elif split_sub_dir and len(split_sub_dir) > 1:
                            split_sub_dir[1] = unify_dir(replcae_dir_name)
                        file_dir = os.path.join(drive, SEP.join(split_sub_dir))
                # create dir
                try:
                    if not os.path.isdir(file_dir):
                        os.makedirs(file_dir)
                except WindowsError as e:
                    raise WindowsError("Fail to makedirs: %s" % file_dir)
                outfile_name = os.path.join(file_dir, header[1])
                open_mode = 'wb'
            else:  # other block of file
                open_mode = 'ab'
                # outfile_name should not be None
                if not outfile_name:
                    raise AssertionError('block missing')
            # 保存文件信息
            with open(outfile_name, open_mode) as outfile:
                content = infile.read(header[-1])
                outfile.write(content)
                outfile.flush()
                del content

        infile.close()
        self.ok = True


# 将命令行指令翻译成Lz4Container对象接口
def api(dir_name, file_name, ctype):
    if ctype == 'c':
        lz4app = Lz4Container(ctype, dir_name=dir_name, file_name=file_name)
        lz4app.compress()
    elif ctype in ('x', 'l'):
        lz4app = Lz4Container(ctype, dir_name=dir_name, file_name=file_name)
        lz4app.decompress()
    else:
        raise TypeError("ValueError: Invalid mode ('%s')" % ctype)


def cmd():
    from docopt import docopt
    args = docopt(__doc__)

    # compression
    if args.get('-c'):
        ctype = 'c'

    # decompression
    elif args.get('-x'):
        ctype = 'x'

    # list
    elif args.get('-l'):
        ctype = 'l'
    api(args.get('<dir_name>'), args.get('<dir_name.lz4r>'), ctype)


if __name__ == '__main__':
    cmd()

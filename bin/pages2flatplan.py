#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import subprocess
from math import sqrt, ceil
import StringIO

from PIL import Image
from git import Repo

def commits(repo_path):
    repo = Repo(repo_path)
    origin = repo.remotes.origin
    origin.fetch()

    commits = reversed([ c for c in repo.iter_commits('master') ])

    for commit in commits:
        commit.checkout()
        print commit, time.asctime(time.gmtime(commit.committed_date))
        print os.listdir(os.path.join(repo_path, 'latex'))

def pdf2pngpages(pdf_fn, output_fn='page-%03d.png', output_dir='.'):

    output_png = os.path.join(output_dir, output_fn)
    i = 0
    result = 0
    pages = [ ]
    while result == 0:
        output_file = output_png % (i,)
        cmd = ['convert',
               '-density', '150',
               '{0}[{1}]'.format(pdf_fn, i),
               '-background', 'white',
               '-alpha', 'remove',
               '-resize', '600x',
               '-quality', '100',
               '-sharpen', '0x1.0',
               output_file]
        try:
            if not os.path.exists(output_file):
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            pages.append(output_file)
            sys.stderr.write('.')
            i += 1
        except subprocess.CalledProcessError, exception:
            result = exception.returncode
            if re.search(r'Requested FirstPage is greater than the number of pages in the file', exception.output):
                print ''
            else:
                raise exception
    print "Processed {0} pages.".format(i)
    return pages

def get_pages(page_dir):
    pages = [ ]
    for fn in os.listdir(page_dir):
        base, ext = os.path.splitext(fn)
        if ext.lower() == '.png':
            abs_fn = os.path.join(page_dir, fn)
            pages.append(abs_fn)
    
    return pages

def page_grid(pages, output_size):
    p0 = Image.open(pages[0])
    # We just assume that all pages are the same size.
    page_size = p0.size
    print p0.mode

    o_ratio = output_size[0] / float(output_size[1])
    p_ratio = page_size[0] / float(page_size[1])
    g_ratio = o_ratio / p_ratio

    page_count = len(pages)
    across = ceil(sqrt(page_count * g_ratio))
    down = ceil(page_count / across)
    grid = (int(across), int(down))

    print grid

    h_gutter = [20, 20]
    min_margin = 4

    usable_width = output_size[0] - (grid[0]-1)*min_margin \
                    - sum(h_gutter)
    page_width = usable_width / grid[0]
    page_height = page_width / p_ratio
    new_page_size = (page_width, int(page_height))
    
    h_margins = min_margin + (usable_width - (new_page_size[0]*grid[0])) / (grid[0]-1)
    h_gutter[1] = (output_size[0] - (new_page_size[0]*grid[0]) - (h_margins*(grid[0]-1))) / 2
    h_gutter[0] = output_size[0] - (new_page_size[0]*grid[0]) - (h_margins*(grid[0]-1)) - h_gutter[1]

    v_gutter = [20, 20]
    if grid[1] > 1:
        v_margins = (output_size[1] - sum(v_gutter) - new_page_size[1]*grid[1]) / (grid[1]-1)
    else:
        v_margins = 0
    v_gutter[1] = (output_size[1] - (new_page_size[1]*grid[1]) - (v_margins*(grid[1]-1))) / 2
    v_gutter[0] = output_size[1] - (new_page_size[1]*grid[1]) - (v_margins*(grid[1]-1)) - v_gutter[1]

    print h_gutter, h_margins, new_page_size
    print v_gutter, v_margins, new_page_size

    # Create a list of positions (top-right corner) for each page in pages.
    page_pos = [ ]
    for i in range(len(pages)):
        x = i % grid[0]
        y = i / grid[0]

        pos = [ h_gutter[0] + x * (new_page_size[0] + h_margins),
                v_gutter[0] + y * (new_page_size[1] + v_margins) ]
        page_pos.append(pos)

    return page_pos, new_page_size

def create_flatplan(pages, page_positions, page_size, output_size):
    fp = Image.new('RGBA', output_size, (0, 0, 0, 255))

    for i in range(len(pages)):
        print pages[i]
        page = Image.open(pages[i])
        fp.paste(page.resize(page_size, Image.ANTIALIAS),
                 tuple(page_positions[i]))

    fp.save('out.png')

def main(argv):
    repo_path = argv[1]
    commits(repo_path)
    return

    page_dir = 'output'

    pages = pdf2pngpages(argv[1], output_dir=page_dir)
#    pages = get_pages(page_dir)

    output_size = (1920, 1080)
    page_positions, page_size = page_grid(pages, output_size)

    create_flatplan(pages, page_positions, page_size, output_size)


if __name__ == '__main__':
    main(sys.argv)

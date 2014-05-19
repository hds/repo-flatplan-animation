#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import subprocess
from math import sqrt, ceil
import StringIO
import shutil

from PIL import Image
from git import Repo

def compile_latex(working_dir, tex_filename):

    cmd = ['/usr/texbin/pdflatex', tex_filename]
    output = subprocess.check_output(cmd, cwd=working_dir,
                                     stderr=subprocess.STDOUT)

    pdf_filename = re.sub(r'\.tex$', '.pdf', tex_filename)
    return pdf_filename

def cache_dir(commit):
    commit_dir = os.path.join('_cache', str(commit))
    if not os.path.exists('_cache'):
        os.mkdir('_cache')
    if not os.path.exists(commit_dir):
        os.mkdir(commit_dir)
    for sub in ['pdf', 'png', 'flatplan']:
        subdir = os.path.join(commit_dir, sub)
        if not os.path.exists(subdir):
            os.mkdir(subdir)
    return commit_dir

def process_commit(repo_path, commit):
    latex_dir = os.path.abspath(os.path.join(repo_path, 'latex'))
    cache = cache_dir(commit)
    output_size = (1920, 1080)
    flatplan = None
    if os.path.exists(latex_dir):
        tex_fn = None
        for fn in os.listdir(latex_dir):
            if fn.endswith('.tex'):
                tex_fn = fn
                break
        if tex_fn is None:
            print "No .tex file found in 'latex' directory."
            return
        pdf_file = compile_latex(latex_dir, tex_fn)
        pdf_cache = os.path.join(cache, 'pdf', pdf_file)
        shutil.copyfile(os.path.join(latex_dir, pdf_file), pdf_cache)

        png_dir = os.path.join(cache, 'png')
        pages = pdf2pngpages(pdf_cache, output_dir=png_dir)

        page_positions, page_size = page_grid(pages, output_size)

        flatplan = os.path.join(cache, 'flatplan', 'flatplan.png')
        create_flatplan(pages, page_positions, page_size, output_size, flatplan)
    else:
        print "There's no 'latex' directory"

    return flatplan

def create_pages(repo_path, commit):
    latex_dir = os.path.abspath(os.path.join(repo_path, 'latex'))
    cache = cache_dir(commit)
    png_dir = os.path.join(cache, 'png')
    pages = [ os.path.join(png_dir, f) for f in os.listdir(png_dir) ]
    if len(pages) > 0:
        print '+' * len(pages)
    elif os.path.exists(latex_dir):
        tex_fn = None
        for fn in os.listdir(latex_dir):
            if fn.endswith('.tex'):
                tex_fn = fn
                break
        if tex_fn is None:
            print "No .tex file found in 'latex' directory."
            return
        pdf_file = compile_latex(latex_dir, tex_fn)
        pdf_cache = os.path.join(cache, 'pdf', pdf_file)
        shutil.copyfile(os.path.join(latex_dir, pdf_file), pdf_cache)

        png_dir = os.path.join(cache, 'png')
        pages = pdf2pngpages(pdf_cache, output_dir=png_dir)
    else:
        print "There's no 'latex' directory"

    return pages

def commits(repo_path):
    repo = Repo(repo_path)
    origin = repo.remotes.origin
    repo.git.checkout('master')
    repo.git.clean('-f', '-d')
    origin.fetch()
    origin.pull()

    commits = reversed([ c for c in repo.iter_commits('master') ])
    commit_pages = [ ]

    for commit in commits:
        repo.git.checkout(commit)
        repo.git.clean('-f', '-d')

        print commit, time.asctime(time.gmtime(commit.committed_date))

        pages = create_pages(repo_path, commit)
        if len(pages) > 0:
            commit_pages.append({'pages': pages, 'commit': commit})

    output_size = (1920, 1080)
    page_counts = [ len(cp['pages']) for cp in commit_pages ]
    ind = page_counts.index(max(page_counts))
    max_pages = commit_pages[ind]['pages']
    page_positions, page_size, output_size = page_grid(max_pages, output_size)
    count = 0
    for cp in commit_pages:

        cache = cache_dir(cp['commit'])
        flatplan = os.path.join(cache, 'flatplan', 'flatplan.png')
        create_flatplan(cp['pages'], page_positions, page_size,
                        output_size, flatplan)

        if flatplan is not None:
            shutil.copyfile(flatplan,
                            os.path.join('out', 'flatplan-%03d.png' % count))
        count += 1


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
    #print "Processed {0} pages.".format(i)
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

    o_ratio = output_size[0] / float(output_size[1])
    p_ratio = page_size[0] / float(page_size[1])
    g_ratio = o_ratio / p_ratio

    page_count = len(pages)
    across = ceil(sqrt(page_count * g_ratio))
    down = ceil(page_count / across)
    grid = (int(across), int(down))

#    print output_size, page_size
#    print o_ratio, p_ratio, g_ratio
#    print page_count, sqrt(page_count * g_ratio)

    h_gutter = [20, 20]
    v_gutter = [20, 20]
    min_margin = 10

    usable_width = output_size[0] - (grid[0]-1)*min_margin \
                    - sum(h_gutter)
    usable_height = output_size[1] - (grid[1]-1)*min_margin \
                    - sum(v_gutter)
    if usable_width / grid[0] < p_ratio * (usable_height / grid[1]):
        page_width = usable_width / grid[0]
        page_height = int(page_width / p_ratio)
    else:
        page_height = usable_height / grid[1]
        page_width = int(page_height * p_ratio)
        
    new_page_size = (page_width, page_height)
    
    h_margins = min_margin
    v_margins = min_margin

    output_size = (sum(h_gutter) - min_margin +
                    grid[0]*(new_page_size[0] + min_margin),
                   sum(v_gutter) - min_margin +
                    grid[1]*(new_page_size[1] + min_margin))

#    h_margins = min_margin + (usable_width - (new_page_size[0]*grid[0])) / (grid[0]-1)
#    h_gutter[1] = (output_size[0] - (new_page_size[0]*grid[0]) - (h_margins*(grid[0]-1))) / 2
#    h_gutter[0] = output_size[0] - (new_page_size[0]*grid[0]) - (h_margins*(grid[0]-1)) - h_gutter[1]
#
#    if grid[1] > 1:
#        v_margins = (output_size[1] - sum(v_gutter) - new_page_size[1]*grid[1]) / (grid[1]-1)
#    else:
#        v_margins = 0
#    v_gutter[1] = (output_size[1] - (new_page_size[1]*grid[1]) - (v_margins*(grid[1]-1))) / 2
#    v_gutter[0] = output_size[1] - (new_page_size[1]*grid[1]) - (v_margins*(grid[1]-1)) - v_gutter[1]

    # Create a list of positions (top-right corner) for each page in pages.
    page_pos = [ ]
    for i in range(len(pages)):
        x = i % grid[0]
        y = i / grid[0]

        pos = [ h_gutter[0] + x * (new_page_size[0] + h_margins),
                v_gutter[0] + y * (new_page_size[1] + v_margins) ]
        page_pos.append(pos)

#    print new_page_size
#    print page_pos
    return page_pos, new_page_size, output_size

def create_flatplan(pages, page_positions, page_size, output_size, output_file):
    fp = Image.new('RGBA', output_size, (0, 0, 0, 0))

    for i in range(len(pages)):
        page = Image.open(pages[i])
        fp.paste(page.resize(page_size, Image.ANTIALIAS),
                 tuple(page_positions[i]))

    fp.save(output_file)

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

#!/usr/bin/env python

import collections
import importlib.util
import logging
import os
import re


log = logging.getLogger(__name__)

TOC_MAX_DEPTH = int(os.environ.get('TOC_MAX_DEPTH', '3'))
LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING')
DOCS_DIR = os.environ.get('DOCS_DIR', 'class_materials')

AUTO_SECTION_TAGS = ('<!-- begin auto-generated {0} section -->', '<!-- end auto-generated section -->')
TITLE_OPEN_TAG = AUTO_SECTION_TAGS[0].format('title')
NAV_OPEN_TAG = AUTO_SECTION_TAGS[0].format('nav-links')

TITLE_CONTENT = '{OPEN_TAG}\n# {title}\n{CLOSE_TAG}\n\n\n'
NAV_CONTENT = '\n\n\n{0}\n'.format('''{OPEN_TAG}
| Previous | Up | Next |
|:---------|:---:|-----:|
| [{prev_title}]({prev_url}) | [{up_title}]({up_url}) | [{next_title}]({next_url}) |
{CLOSE_TAG}''')

TITLE_REGEX = re.compile(f'\s*{TITLE_OPEN_TAG}\s*.*?\s*{AUTO_SECTION_TAGS[1]}\s*', re.MULTILINE | re.DOTALL)
NAV_REGEX = re.compile(f'\s*{NAV_OPEN_TAG}\s*.*?\s*{AUTO_SECTION_TAGS[1]}\s*', re.MULTILINE | re.DOTALL)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, DOCS_DIR)

toc_spec = importlib.util.spec_from_file_location('toc', os.path.join(CONTENT_DIR, '_toc.py'))
toc = importlib.util.module_from_spec(toc_spec)
toc_spec.loader.exec_module(toc)
HIERARCHY = toc.HIERARCHY
ROOT_ELEMENT = HIERARCHY[0][1]

Node = collections.namedtuple('Node', ['index', 'title', 'filename', 'parent', 'children'])

ALL_NODES = []
NODES_BY_PATH = {}


def make_subtree(item, parent):
    log.debug('creating node for %s', item[1] if item[1] else 'ROOT')
    assert item[1] not in NODES_BY_PATH or log.critical('repeated page: %s', item[1])
    ALL_NODES.append(None)
    node = Node(
        index=len(ALL_NODES) - 1,
        title=item[0],
        filename=item[1],
        parent=parent[1] if parent else None,
        children=tuple(make_subtree(x, item) for x in item[2]),
    )
    ALL_NODES[node.index] = node
    NODES_BY_PATH[node.filename] = node
    return node


def rewrite_file(fname, root):
    fpath = os.path.join(CONTENT_DIR, fname)
    with open(fpath) as fin:
        content = fin.read()
    node = NODES_BY_PATH[fname]
    log.debug('node %d: %s (%s)', node.index, node.title, node.parent)
    new_title = TITLE_CONTENT.format(title=node.title, OPEN_TAG=TITLE_OPEN_TAG, CLOSE_TAG=AUTO_SECTION_TAGS[1])
    updated = re.sub(TITLE_REGEX, new_title, content)
    log.debug('title updated: %s', updated != content)
    content = updated
    parent = NODES_BY_PATH[node.parent] if node.parent else root
    log.debug('parent: %s', parent.title)
    prev = ALL_NODES[node.index-1] if node.index > 0 else root
    log.debug('prev: %s', prev.title)
    nxt = ALL_NODES[node.index+1] if node.index < len(ALL_NODES) - 1 else root
    log.debug('next: %s', nxt.title)
    new_nav = NAV_CONTENT.format(
        prev_title=prev.title,
        prev_url=prev.filename,
        up_title=parent.title if parent else None,
        up_url=parent.filename if parent else None,
        next_title=nxt.title,
        next_url=nxt.filename,
        OPEN_TAG=NAV_OPEN_TAG,
        CLOSE_TAG=AUTO_SECTION_TAGS[1],
    )
    log.debug('nav regex: %s', NAV_REGEX)
    log.debug('updated nav: %s', new_nav)
    updated = re.sub(NAV_REGEX, new_nav, content)
    log.debug('nav updated: %s', updated != content)
    with open(fpath, 'w') as fout:
        fout.write(updated)


def write_toc_node(node, level, fout):
    if level >= TOC_MAX_DEPTH:
        return
    log.info('writing table of contents node: %d -> %s', level, node.title)
    fout.write('{0}1. [{1}]({2})\n'.format(' ' * level * 4, node.title, node.filename))
    for child in node.children:
        write_toc_node(child, level + 1, fout)


def rewrite_toc(root):
    log.info('writing table of contents file')
    with open(os.path.join(CONTENT_DIR, root.filename), 'w') as fout:
        fout.write('# Table of Contents\n\n')
        for node in root.children:
            write_toc_node(node, 0, fout)


def main():
    log.info('building page hierarchy tree')
    tree = make_subtree(HIERARCHY, None)
    log.debug('tree: %s', tree)
    log.debug('pages by path: %s', NODES_BY_PATH)
    log.info('nodes count: %d', len(ALL_NODES))
    log.debug('count method 2: %d', len(NODES_BY_PATH))
    for node in ALL_NODES:
        log.info('%d -> %s (%s)', node.index, node.title, node.filename)
    root = NODES_BY_PATH[HIERARCHY[1]]
    log.info('root: %s', root.title)
    all_filenames = set(k for k in NODES_BY_PATH.keys() if k)
    log.info('loading files from: %s', CONTENT_DIR)
    all_files = set(f'./{fname}' for fname in os.listdir(CONTENT_DIR) if re.match('[^.].*\.md', fname))
    log.debug('files: %s', all_files)
    for fname in sorted(all_filenames):
        if fname not in all_files:
            log.critical('hierarchy refers to non-existent page: %s', fname)
            raise Exception
    for fname in list(all_files):
        log.info('fname: %s', fname)
        if fname in NODES_BY_PATH and fname != root.title:
            rewrite_file(fname, root)
        else:
            log.warning('skipping file %s (not in page structure)', fname)
    rewrite_toc(root)


if __name__ == '__main__':
    log.addHandler(logging.StreamHandler())
    log.setLevel(getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')))
    main()

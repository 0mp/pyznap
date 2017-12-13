"""
Created on Wed Dec 06 2017

@author: cythoning

Take snapshots
"""

from datetime import datetime
from subprocess import CalledProcessError
from utils import Remote, parse_name
import pyzfs as zfs
from process import DatasetBusyError, DatasetNotFoundError


def take_snap(filesystem, conf):
    """Takes snapshots of a single filesystem according to conf"""

    logtime = lambda: datetime.now().strftime('%b %d %H:%M:%S')
    now = lambda: datetime.now()

    ssh = filesystem.ssh
    if ssh:
        name_log = '{:s}@{:s}:{:s}'.format(ssh.user, ssh.host, filesystem.name)
    else:
        name_log = filesystem.name

    # print('{:s} INFO: Taking snapshots on {:s}...'.format(logtime(), name_log))

    snapshots = {'hourly': [], 'daily': [], 'weekly': [], 'monthly': [], 'yearly': []}
    for snap in filesystem.snapshots():
        # Ignore snapshots not taken with pyznap or sanoid
        if not snap.name.split('@')[1].startswith(('pyznap', 'autosnap')):
            continue
        snap_time = datetime.fromtimestamp(int(snap.getprop('creation')[0]))
        snap_type = snap.name.split('_')[-1]

        try:
            snapshots[snap_type].append((snap, snap_time))
        except KeyError:
            continue

    # Reverse sort by time taken
    for snaps in snapshots.values():
        snaps.reverse()

    snapname = lambda: 'pyznap_{:s}_'.format(now().strftime('%Y-%m-%d_%H:%M:%S'))

    if conf['yearly'] and (not snapshots['yearly'] or
                           snapshots['yearly'][0][1].year != now().year):
        print('{:s} INFO: Taking snapshot {:s}@{:s}...'.format(logtime(), name_log, snapname() + 'yearly'))
        try:
            filesystem.snapshot(snapname=snapname() + 'yearly', recursive=True)
        except (DatasetBusyError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))

    if conf['monthly'] and (not snapshots['monthly'] or
                            snapshots['monthly'][0][1].month != now().month):
        print('{:s} INFO: Taking snapshot {:s}@{:s}...'.format(logtime(), name_log, snapname() + 'monthly'))
        try:
            filesystem.snapshot(snapname=snapname() + 'monthly', recursive=True)
        except (DatasetBusyError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))

    if conf['weekly'] and (not snapshots['weekly'] or
                           snapshots['weekly'][0][1].isocalendar()[1] != now().isocalendar()[1]):
        print('{:s} INFO: Taking snapshot {:s}@{:s}...'.format(logtime(), name_log, snapname() + 'weekly'))
        try:
            filesystem.snapshot(snapname=snapname() + 'weekly', recursive=True)
        except (DatasetBusyError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))

    if conf['daily'] and (not snapshots['daily'] or
                          snapshots['daily'][0][1].day != now().day):
        print('{:s} INFO: Taking snapshot {:s}@{:s}...'.format(logtime(), name_log, snapname() + 'daily'))
        try:
            filesystem.snapshot(snapname=snapname() + 'daily', recursive=True)
        except (DatasetBusyError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))

    if conf['hourly'] and (not snapshots['hourly'] or
                           snapshots['hourly'][0][1].hour != now().hour):
        print('{:s} INFO: Taking snapshot {:s}@{:s}...'.format(logtime(), name_log, snapname() + 'hourly'))
        try:
            filesystem.snapshot(snapname=snapname() + 'hourly', recursive=True)
        except (DatasetBusyError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))


def take_config(config):
    """Takes snapshots according to strategy given in config"""

    logtime = lambda: datetime.now().strftime('%b %d %H:%M:%S')
    print('{:s} INFO: Taking snapshots...'.format(logtime()))

    for conf in config:
        if not conf.get('snap', None):
            continue

        name = conf['name']
        try:
            _type, fsname, user, host, port = parse_name(name)
        except ValueError as err:
            print('{:s} ERROR: Could not parse {:s}: {}...'
                  .format(logtime(), name, err))
            continue

        if _type == 'ssh':
            try:
                ssh = Remote(user, host, port, conf['key'])
            except FileNotFoundError as err:
                print('{:s} ERROR: {} is not a valid ssh key file...'.format(logtime(), err))
                continue
            if not ssh.test():
                continue
        else:
            ssh = None

        try:
            # Children includes the base filesystem (filesystem)
            children = zfs.find(path=fsname, types=['filesystem', 'volume'], ssh=ssh)
        except (ValueError, DatasetNotFoundError, CalledProcessError) as err:
            print('{:s} ERROR: {}'.format(logtime(), err))
            continue

        # Take recursive snapshot of parent filesystem
        take_snap(children[0], conf)
        # Take snapshot of all children that don't have all snapshots yet
        for child in children[1:]:
            # Check if any of the parents (but child of base filesystem) have a config entry
            for parent in children[1:]:
                if ssh:
                    parent_name = 'ssh:{:d}:{:s}@{:s}:{:s}'.format(port, user, host, parent.name)
                else:
                    parent_name = parent.name
                # Skip if any parent entry already in config
                if (child.name.startswith(parent.name) and
                        parent_name in [entry['name'] for entry in config]):
                    break
            else:
                take_snap(child, conf)

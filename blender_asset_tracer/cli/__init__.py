"""Commandline entry points."""

import argparse
import datetime
import logging
import time

from . import common, pack, list_deps


def cli_main():
    parser = argparse.ArgumentParser(description='BAT: Blender Asset Tracer')
    common.add_flag(parser, 'profile', help='Run the profiler, write to bam.prof')

    # func is set by subparsers to indicate which function to run.
    parser.set_defaults(func=None,
                        loglevel=logging.WARNING)
    loggroup = parser.add_mutually_exclusive_group()
    loggroup.add_argument('-v', '--verbose', dest='loglevel',
                          action='store_const', const=logging.INFO,
                          help='Log INFO level and higher')
    loggroup.add_argument('-d', '--debug', dest='loglevel',
                          action='store_const', const=logging.DEBUG,
                          help='Log everything')
    loggroup.add_argument('-q', '--quiet', dest='loglevel',
                          action='store_const', const=logging.ERROR,
                          help='Log at ERROR level and higher')
    subparsers = parser.add_subparsers(help='sub-command help')

    pack.add_parser(subparsers)
    list_deps.add_parser(subparsers)

    args = parser.parse_args()
    config_logging(args)

    from blender_asset_tracer import __version__
    log = logging.getLogger(__name__)
    log.debug('Running BAT version %s', __version__)

    if not args.func:
        parser.error('No subcommand was given')

    start_time = time.time()
    if args.profile:
        import cProfile

        prof_fname = 'bam.prof'
        cProfile.runctx('args.func(args)',
                        globals=globals(),
                        locals=locals(),
                        filename=prof_fname)
        print('Profiler exported data to', prof_fname)
        print('Run "pyprof2calltree -i %r -k" to convert and open in KCacheGrind' % prof_fname)
    else:
        retval = args.func(args)
    duration = datetime.timedelta(seconds=time.time() - start_time)
    log.info('Command took %s to complete', duration)


def config_logging(args):
    """Configures the logging system based on CLI arguments."""

    logging.basicConfig(
        level=args.loglevel,
        format='%(asctime)-15s %(levelname)8s %(name)-40s %(message)s',
    )

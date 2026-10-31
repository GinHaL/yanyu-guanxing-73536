# -*- coding: utf-8 -*-
"""烟雨观星 HAR 存档工具入口：角色列表、n 导入、q 退出。"""
import argparse
import sys

from . import __version__, layer2, ui, wizard


def build_parser():
    parser = argparse.ArgumentParser(
        prog="yyjh", description=f"烟雨观星 HAR 存档工具 v{__version__}"
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细错误")
    sub = parser.add_subparsers(dest="command")
    wizard.add_parsers(sub)
    layer2.add_parsers(sub)
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # 支持 python run.py -v / python run.py capture B.har -v。
    verbose = any(a in ("-v", "--verbose") for a in argv)
    argv = [a for a in argv if a not in ("-v", "--verbose")]
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "-V", "--version")):
        argv.insert(0, "start")
    parser = build_parser()
    args = parser.parse_args(argv)
    ui.setup_console()
    ui.configure(verbose=verbose)
    fn = getattr(args, "func", None)
    if fn is None:
        parser.print_help()
        return 0
    try:
        result = fn(args)
        return result if isinstance(result, int) else 0
    except ui.Cancelled:
        return 0
    except KeyboardInterrupt:
        ui.warn("已取消")
        return 130
    except ui.UserError as exc:
        ui.report_error(exc, verbose)
        return 2
    except (OSError, ValueError) as exc:
        ui.report_error(ui.UserError(str(exc)), verbose)
        return 2


if __name__ == "__main__":
    sys.exit(main())

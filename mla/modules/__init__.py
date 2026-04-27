"""Module registry for MyLittleAnsible.

Author: Sandro Bakuradze.
"""

from typing import Dict, Type

from .apt import AptModule
from .base import BaseModule
from .command import CommandModule
from .copy import CopyModule
from .debug import DebugModule
from .file import FileModule
from .git import GitModule
from .lineinfile import LineInFileModule
from .service import ServiceModule
from .sysctl import SysctlModule
from .template import TemplateModule
from .user import UserModule

MODULES: Dict[str, Type[BaseModule]] = {
    cls.name: cls
    for cls in (
        AptModule,
        CommandModule,
        CopyModule,
        DebugModule,
        FileModule,
        GitModule,
        LineInFileModule,
        ServiceModule,
        SysctlModule,
        TemplateModule,
        UserModule,
    )
}

__all__ = ["BaseModule", "MODULES"]

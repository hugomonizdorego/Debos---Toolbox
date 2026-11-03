"""All pages, in navigation order."""

from .about import About
from .cleaner import Cleaner
from .customizer import Customizer
from .dashboard import Dashboard
from .defaultapps import DefaultApps
from .desktops import Desktops
from .desktoptweaks import DesktopTweaks
from .drivers import Drivers
from .kernels import Kernels
from .network import Network
from .recommendations import Recommendations
from .repositories import Repositories
from .search import Search
from .software import Software
from .sources_editor import SourcesEditor
from .startup import Startup
from .systemtweaks import SystemTweaks
from .templates import Templates
from .uninstall import Uninstall
from .updates import Updates

PAGES = {cls.ID: cls for cls in (Dashboard, Recommendations, Cleaner, Updates, Repositories, SourcesEditor, Software, Uninstall,
                                 Desktops, Kernels, Drivers, Network, SystemTweaks, DesktopTweaks, Startup, DefaultApps, Templates,
                                 Customizer, About, Search)}

"""
Akaion Banner and ASCII Art

Brand colors and visual elements for terminal output.
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Akaion brand colors
AKAION_GRADIENT = ["#00D9FF", "#0099FF", "#0066FF", "#0033FF"]
AKAION_CYAN = "#00D9FF"
AKAION_BLUE = "#0066FF"
AKAION_DARK = "#0033FF"


def print_banner():
    """Print the Akaion banner with brand colors"""
    banner = r"""
    ___    __   __ ___    ____  _   __
   /   |  / /__/ //   |  /  _/ / | / /
  / /| | / //_/ // /| |  / /  /  |/ / 
 / ___ |/ ,< / // ___ |_/ /  / /|  /  
/_/  |_/_/|_/_//_/  |_/___/ /_/ |_/   
                                       
    """
    
    # Create gradient text
    lines = banner.split('\n')
    text = Text()
    
    for i, line in enumerate(lines):
        # Calculate color index based on line position
        color_idx = min(i * len(AKAION_GRADIENT) // len(lines), len(AKAION_GRADIENT) - 1)
        text.append(line + '\n', style=f"bold {AKAION_GRADIENT[color_idx]}")
    
    console.print(text, end='')


def print_runner_banner():
    """Print the full runner startup banner"""
    banner = r"""
    ___    __   __ ___    ____  _   __
   /   |  / /__/ //   |  /  _/ / | / /
  / /| | / //_/ // /| |  / /  /  |/ / 
 / ___ |/ ,< / // ___ |_/ /  / /|  /  
/_/  |_/_/|_/_//_/  |_/___/ /_/ |_/   
    """
    
    # Create gradient banner
    lines = banner.split('\n')
    gradient_text = Text()
    
    for i, line in enumerate(lines):
        if line.strip():  # Skip empty lines
            # Gradient from cyan to blue
            color_idx = min(i * len(AKAION_GRADIENT) // len(lines), len(AKAION_GRADIENT) - 1)
            gradient_text.append(line + '\n', style=f"bold {AKAION_GRADIENT[color_idx]}")
    
    # Subtitle
    subtitle = Text()
    subtitle.append("🚀 ", style="bold yellow")
    subtitle.append("RUNNER ", style=f"bold {AKAION_CYAN}")
    subtitle.append("v0.1.0", style=f"dim {AKAION_BLUE}")
    subtitle.append(" | ", style="dim white")
    subtitle.append("Local Agent Execution Platform", style=f"italic {AKAION_BLUE}")
    
    # Print banner
    console.print()
    console.print(gradient_text, end='')
    console.print(subtitle, justify="center")
    console.print()


def print_runner_box():
    """Print a styled box with runner info"""
    text = Text()
    text.append("🚀 ", style="bold yellow")
    text.append("AKAION", style=f"bold {AKAION_CYAN}")
    text.append(" RUNNER\n", style=f"bold {AKAION_BLUE}")
    text.append("Local Agent Execution Platform", style=f"italic dim {AKAION_BLUE}")
    
    panel = Panel(
        text,
        border_style=AKAION_CYAN,
        padding=(1, 2),
        title="[bold cyan]v0.1.0[/bold cyan]",
        subtitle="[dim]🔗 Connected to Cloud[/dim]"
    )
    
    console.print(panel)


def print_startup_info(runner_id: str, cloud_url: str, polling_interval: int):
    """Print startup information"""
    from rich.table import Table
    
    table = Table(show_header=False, border_style=AKAION_BLUE, padding=(0, 1))
    table.add_column(style=f"bold {AKAION_CYAN}")
    table.add_column(style="white")
    
    table.add_row("🆔 Runner ID", runner_id)
    table.add_row("🌐 Cloud", cloud_url)
    table.add_row("⏱️  Poll Interval", f"{polling_interval}s")
    table.add_row("🔐 Auth", "✓ Authenticated")
    
    console.print(table)
    console.print()


def print_status_header():
    """Print status check header"""
    text = Text()
    text.append("⚡ ", style="bold yellow")
    text.append("AKAION", style=f"bold {AKAION_CYAN}")
    text.append(" Status Check", style=f"bold {AKAION_BLUE}")
    console.print(text)
    console.print()


def print_simple_logo():
    """Print a simple one-line logo"""
    text = Text()
    text.append("⚡ ", style="bold yellow")
    text.append("AKAION", style=f"bold {AKAION_CYAN}")
    text.append(" RUNNER", style=f"bold {AKAION_BLUE}")
    console.print(text)

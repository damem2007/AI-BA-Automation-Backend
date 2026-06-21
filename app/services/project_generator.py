import re
import secrets
import string
from typing import Tuple

AVATAR_COLORS = [
    "#16A34A",  # green-600
    "#2563EB",  # blue-600
    "#DC2626",  # red-600
    "#EA580C",  # orange-600
    "#7C3AED",  # violet-600
    "#0891B2",  # cyan-600
    "#DB2777",  # pink-600
    "#65A30D",  # lime-600
    "#D97706",  # amber-600
    "#059669",  # emerald-600
    "#4F46E5",  # indigo-600
    "#9333EA",  # purple-600
    "#C026D3",  # fuchsia-600
    "#E11D48",  # rose-600
    "#0D9488",  # teal-600
    "#0284C7",  # sky-600
    "#CA8A04",  # yellow-600
    "#57534E",  # stone-600
    "#52525B",  # zinc-600
    "#4B5563",  # gray-600
    "#475569",  # slate-600
    "#B91C1C",  # deep-red
    "#C2410C",  # deep-orange
    "#A16207",  # ochre
    "#4D7C0F",  # olive-green
    "#047857",  # deep-emerald
    "#0F766E",  # deep-teal
    "#0369A1",  # deep-sky
    "#1D4ED8",  # royal-blue
    "#6D28D9",  # deep-violet
    "#15803D",  # green-700
    "#1E40AF",  # blue-800
    "#991B1B",  # red-800
    "#9A3412",  # orange-800
    "#5B21B6",  # violet-800
    "#155E75",  # cyan-800
    "#9D174D",  # pink-800
    "#3F6212",  # lime-800
    "#92400E",  # amber-800
    "#065F46",  # emerald-800
    "#3730A3",  # indigo-800
    "#6B21A8",  # purple-800
    "#86198F",  # fuchsia-800
    "#9F1239",  # rose-800
    "#115E59",  # teal-800
    "#075985",  # sky-800
    "#854D0E",  # yellow-800
    "#44403C",  # stone-700
    "#3F3F46",  # zinc-700
    "#374151",  # gray-700
    "#334155",  # slate-700
    "#166534",  # forest-green
    "#1E3A8A",  # navy-blue
    "#7F1D1D",  # burgundy
    "#7C2D12",  # burnt-orange
    "#581C87",  # dark-purple
    "#164E63",  # deep-cyan
    "#831843",  # deep-pink
    "#365314",  # deep-lime
    "#78350F",  # dark-amber
    "#064E3B",  # dark-emerald
    "#312E81",  # dark-indigo
    "#701A75",  # dark-fuchsia
    "#881337",  # dark-rose
    "#134E4A",  # dark-teal
    "#0C4A6E",  # dark-sky
    "#713F12",  # dark-yellow
    "#292524",  # dark-stone
    "#27272A",  # dark-zinc
    "#1F2937",  # dark-gray
]
STOP_WORDS = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "it"}
def generate_project_code(project_name: str) -> str:
    """
    Generate unique project code: PROJECT-ABC123
    Format: [INITIALS]-[RANDOM]
    """
    # Get first 3 letters from project name
    initials = "".join(
        word[0].upper() for word in project_name.split()[:2]
    ).ljust(3, "X")[:3]
    
    # Generate 6-char random suffix
    random_suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    
    return f"{initials}-{random_suffix}"

def generate_avatar_color() -> str:
    """Return random avatar color from predefined palette"""
    return secrets.choice(AVATAR_COLORS)

def get_initials(project_name: str) -> str:
    """Extract 2-4 character initials from project name
    - Single word: returns first 2 letters
    - Multiple words (split by space, '-', or '_'): returns first letter of each word
    - Stop words (e.g. 'and', 'of', 'in') are skipped
    - Maximum 4 characters
    """
    #words = project_name.split()
    if not project_name:
        return "PR"
    words = re.split(r'[ \-_]+', project_name.strip())
    words = [w for w in words if w]  # Remove empty strings
    if not words:
        return "PR"
    #if len(words) == 1:
    #    initials = words[0][:2].upper()
   # else:
    filtered = [w for w in words if w.lower() not in STOP_WORDS]
    # If all words were stop words, fall back to unfiltered
    if not filtered:
        filtered = words
    if len(filtered) == 1:
        return filtered[0][:2].upper()
    initials = ''.join(word[0] for word in filtered).upper()[:4]
    return initials

def generate_artifact_avatar(project_name: str) -> Tuple[str, str]:
    """Generate both color and initials"""
    return generate_avatar_color(), get_initials(project_name)


def normalize_project_code(value: str) -> str:
    """Normalize a user-provided project code to an enterprise-safe identifier."""
    return re.sub(r"[^A-Z0-9-]+", "-", value.strip().upper()).strip("-")

# Usage:
# code = generate_project_code("Business Process Automation")  # → "BPA-X8K2Q9"
# color = generate_avatar_color()  # → "#16A34A"
# initials = get_initials("Business Process Automation")  # → "BP"

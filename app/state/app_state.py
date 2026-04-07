from dataclasses import dataclass
from typing import Optional


@dataclass
class AppState:
    connected: bool = False
    current_recipe: Optional[dict] = None
    selected_recipe_name: Optional[str] = None
    jog_active: bool = False
    jog_direction: str = "right"
    manual_activo: bool = False
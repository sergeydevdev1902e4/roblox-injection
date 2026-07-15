import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


class RbxlxPatchError(Exception):
    pass


class RbxlxPatcher:
    """Traverses and patches Roblox XML place files (.rbxlx)."""

    def __init__(self, xml_path: Path | str):
        self.path = Path(xml_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Target place file does not exist: {self.path}")
        try:
            self.tree = ET.parse(self.path)
        except ET.ParseError as e:
            raise RbxlxPatchError(f"Malformed XML in {self.path}: {e}") from e
        self.root = self.tree.getroot()
        if self.root.tag != "roblox":
            raise RbxlxPatchError(f"Expected root element <roblox>, got <{self.root.tag}>")

    def _generate_referent(self, path_str: str) -> str:
        # Roblox Studio referents are arbitrary strings like 'RBX8F2B7A...'
        digest = hashlib.md5(path_str.encode("utf-8")).hexdigest().upper()[:16]
        return f"RBX_INJECT_{digest}"

    def find_service_or_child(self, parent: ET.Element, name: str) -> ET.Element | None:
        # Top-level items in .rbxlx can match either class name or Name property
        for item in parent.findall("Item"):
            if item.get("class") == name:
                return item
            props = item.find("Properties")
            if props is not None:
                for str_elem in props.findall("string"):
                    if str_elem.get("name") == "Name" and str_elem.text == name:
                        return item
        return None

    def _get_or_create_properties(self, item: ET.Element) -> ET.Element:
        props = item.find("Properties")
        if props is None:
            props = ET.Element("Properties")
            item.insert(0, props)
        return props

    def patch_script(
        self, 
        path_str: str, 
        source: str, 
        class_name: str = "ModuleScript", 
        create_missing: bool = True
    ) -> bool:
        parts = [p.strip() for p in path_str.split(".") if p.strip()]
        if not parts:
            return False

        current = self.root
        accumulated_path = []

        for i, part in enumerate(parts):
            accumulated_path.append(part)
            child = self.find_service_or_child(current, part)
            
            if child is None:
                if not create_missing:
                    return False

                is_leaf = (i == len(parts) - 1)
                node_cls = class_name if is_leaf else "Folder"
                ref_id = self._generate_referent(".".join(accumulated_path))
                
                child = ET.SubElement(current, "Item", {"class": node_cls, "referent": ref_id})
                props = self._get_or_create_properties(child)
                
                name_tag = ET.SubElement(props, "string", {"name": "Name"})
                name_tag.text = part

                # Folders and scripts have default boolean attributes in Studio
                if not is_leaf:
                    ET.SubElement(props, "bool", {"name": "AttributesSerialize"}).text = ""
            
            current = child

        # Once we've navigated to the target node, check or update its class
        if current.get("class") != class_name and current != self.root:
            # keep Folder if user accidentally targeted existing folder without forcing
            if current.get("class") not in ("Folder", "Model"):
                current.set("class", class_name)

        props = self._get_or_create_properties(current)
        src_node = None
        for tag in ("ProtectedString", "string"):
            for el in props.findall(tag):
                if el.get("name") == "Source":
                    src_node = el
                    break

        # print(f"DEBUG: node={current.tag} target={path_str} ref={current.get('referent')}")

        if src_node is None:
            src_node = ET.SubElement(props, "ProtectedString", {"name": "Source"})

        src_node.text = source
        return True

    def get_script_source(self, path_str: str) -> str | None:
        parts = [p.strip() for p in path_str.split(".") if p.strip()]
        current = self.root
        for part in parts:
            current = self.find_service_or_child(current, part)
            if current is None:
                return None
        
        props = current.find("Properties")
        if props is None:
            return None
        
        for tag in ("ProtectedString", "string"):
            for el in props.findall(tag):
                if el.get("name") == "Source":
                    return el.text or ""
        return None

    def save(self, out_path: Path | str | None = None) -> None:
        target = Path(out_path) if out_path else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        self.tree.write(target, encoding="utf-8", xml_declaration=True)

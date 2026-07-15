import pytest
import xml.etree.ElementTree as ET
from roblox_injection.xml_patcher import XmlPlacePatcher, PatcherError


SAMPLE_RBXLX = """<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="4">
	<Item class="ServerScriptService" referent="RBX1">
		<Properties>
			<string name="Name">ServerScriptService</string>
		</Properties>
		<Item class="Script" referent="RBX2">
			<Properties>
				<string name="Name">Bootstrap</string>
				<ProtectedString name="Source"><![CDATA[print("original")]]></ProtectedString>
			</Properties>
		</Item>
	</Item>
	<Item class="ReplicatedStorage" referent="RBX3">
		<Properties>
			<string name="Name">ReplicatedStorage</string>
		</Properties>
	</Item>
</roblox>"""


def test_patch_existing_script_source():
    patcher = XmlPlacePatcher.from_string(SAMPLE_RBXLX)
    new_code = "local v = 123\nreturn v"
    
    res = patcher.patch_source(["ServerScriptService", "Bootstrap"], new_code)
    assert res is True

    root = ET.fromstring(patcher.to_string())
    source_node = root.find(".//Item[@class='Script']/Properties/ProtectedString[@name='Source']")
    assert source_node is not None
    assert source_node.text == new_code


def test_patch_non_existent_path_fails_without_create():
    patcher = XmlPlacePatcher.from_string(SAMPLE_RBXLX)
    with pytest.raises(PatcherError, match="Target node not found"):
        patcher.patch_source(["ServerScriptService", "MissingScript"], "-- test", create_missing=False)


def test_auto_create_nested_module_script():
    patcher = XmlPlacePatcher.from_string(SAMPLE_RBXLX)
    new_src = "return { app = 'injected' }"
    path = ["ReplicatedStorage", "Config", "Environment", "BuildVars"]
    
    patcher.patch_source(path, new_src, create_missing=True, class_name="ModuleScript")

    xml_out = patcher.to_string()
    assert "BuildVars" in xml_out
    assert "Environment" in xml_out
    
    root = ET.fromstring(xml_out)
    # verify nesting: ReplicatedStorage -> Config (Folder) -> Environment (Folder) -> BuildVars (ModuleScript)
    rep = root.find(".//Item[@class='ReplicatedStorage']")
    assert rep is not None
    
    cfg = rep.find("./Item[@class='Folder']")
    assert cfg is not None
    assert cfg.find("./Properties/string[@name='Name']").text == "Config"
    
    env = cfg.find("./Item[@class='Folder']")
    assert env is not None
    
    mod = env.find("./Item[@class='ModuleScript']")
    assert mod is not None
    assert mod.find("./Properties/string[@name='Name']").text == "BuildVars"
    assert mod.find("./Properties/ProtectedString[@name='Source']").text == new_src


def test_preserve_custom_referent_tokens():
    patcher = XmlPlacePatcher.from_string(SAMPLE_RBXLX)
    patcher.patch_source(["ServerScriptService", "Bootstrap"], "-- updated")
    
    xml_out = patcher.to_string()
    # existing referents must not be wiped out or mangled
    assert 'referent="RBX1"' in xml_out
    assert 'referent="RBX2"' in xml_out

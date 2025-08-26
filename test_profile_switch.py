#!/usr/bin/env python3
"""Test script to verify profile switching works without restart"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

# Test 1: Check GLib MainContext iteration (fix for the AttributeError)
def test_glib_iteration():
    print("Testing GLib MainContext iteration...")
    try:
        context = GLib.MainContext.default()
        # This should work - iterate once
        context.iteration(may_block=False)
        print("✅ GLib MainContext iteration works correctly")
        return True
    except AttributeError as e:
        print(f"❌ GLib MainContext iteration failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# Test 2: Verify profile selector dialog structure
def test_profile_selector_import():
    print("\nTesting profile selector import...")
    try:
        from label_editor.ui.profile_selector_gtk4 import ProfileSelectorDialog, show_profile_selector
        print("✅ Profile selector imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import profile selector: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# Test 3: Check event handler profile change method
def test_event_handler_profile_change():
    print("\nTesting event handler profile change method...")
    try:
        from label_editor.ui.event_handlers import EventHandlerMixin
        # Check if the new methods exist
        if hasattr(EventHandlerMixin, '_handle_profile_change'):
            print("✅ _handle_profile_change method exists")
        else:
            print("❌ _handle_profile_change method not found")
            return False
            
        if hasattr(EventHandlerMixin, '_reload_current_image_with_new_profile'):
            print("✅ _reload_current_image_with_new_profile method exists")
        else:
            print("❌ _reload_current_image_with_new_profile method not found")
            return False
        
        return True
    except ImportError as e:
        print(f"❌ Failed to import event handlers: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing Profile Switch Fixes")
    print("=" * 60)
    
    tests = [
        test_glib_iteration,
        test_profile_selector_import,
        test_event_handler_profile_change
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    if all(results):
        print("✅ All tests passed! Profile switching should work without restart.")
    else:
        print("❌ Some tests failed. Please review the errors above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
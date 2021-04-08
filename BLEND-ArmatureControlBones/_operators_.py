import bpy
import json
from bpy.props import (StringProperty, BoolProperty, EnumProperty, IntProperty)
from . import _functions_, _properties_

class JK_OT_ACB_Subscribe_Object_Mode(bpy.types.Operator):
    """Subscribes the objects mode switching to the msgbus in order to auto sync editing"""
    bl_idname = "jk.acb_sub_mode"
    bl_label = "Subscribe Object"

    Object: StringProperty(name="Object", description="Name of the object to subscribe", default="")
    
    def execute(self, context):
        _functions_.subscribe_mode_to(bpy.data.objects[self.Object], _functions_.armature_mode_callback)
        return {'FINISHED'}

class JK_OT_Edit_Controls(bpy.types.Operator):
    """Edits the current controls of the armature"""
    bl_idname = "jk.acb_edit_controls"
    bl_label = "Control Bones"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(name="Action", description="What this operator should do to the controls",
        items=[('ADD', 'Add', ""), ('REMOVE', 'Remove', ""), ('UPDATE', 'Update', "")],
        default='ADD')
    
    only_selected: BoolProperty(name="Only Selected", description="Only operate on selected bones",
        default=False, options=set())

    only_deforms: BoolProperty(name="Only Deforms", description="Only operate on deforming bones",
        default=False, options=set())
    
    orient: BoolProperty(name="Orient Controls", description="Attempt to automatically orient control bones. (Useful when operating on bones that are not oriented for Blender)",
        default=False, options=set())

    parent: BoolProperty(name="Parent Deforms", description="Attempt to automatically parent deform bones. (Useful when operating on a broken hierarchy)",
        default=False, options=set())

    def execute(self, context):
        controller = bpy.context.view_layer.objects.active
        deformer = controller.data.jk_acb.armature
        # make sure the operator cannot trigger any auto updates...
        is_auto_updating = controller.data.jk_acb.use_auto_update
        controller.data.jk_acb.use_auto_update = False
        # get the bones we should be operating on...
        bones = _functions_.get_bone_names(self, controller)
        # if we are adding deform bones...
        if self.action == 'ADD':
            # if there is existing deform bone data...
            if controller.data.jk_acb.deforms and controller.data.jk_acb.is_controller:
                # gather them into the bones we should be operating on...
                deforms = json.loads(controller.data.jk_acb.deforms)
                for bone in deforms:
                    control_bb = controller.data.bones.get(bone['name'])
                    # as long as they aren't already in there...
                    if control_bb and control_bb.name not in bones:
                        bones[control_bb.name] = False
            # so we can get a fresh copy of them in order of hierarchy...
            deform_bones = _functions_.get_deform_bones(controller, bones)
            controller.data.jk_acb.deforms = json.dumps(deform_bones)
            # if the armature is already a controller...
            if controller.data.jk_acb.is_controller:
                # just make sure the new deform bones get added...
                _functions_.add_deform_bones(controller, deformer)
            else:
                # if we are using combined armatures...
                if controller.data.jk_acb.use_combined:
                    # just add the deform bones to the controller...
                    _functions_.add_deform_bones(controller, deformer)
                    # and set the pointer and bools... (when combined the controller just references itself)
                    controller.data.jk_acb.is_controller = True
                    controller.data.jk_acb.armature = controller
                    controller.data.jk_acb.is_deformer = True
                    # and subscribe the mode change callback...
                    _functions_.subscribe_mode_to(controller, _functions_.armature_mode_callback)
                else:
                    # otherwise add in the deform armature...
                    _functions_.add_deform_armature(controller)
                    deformer = controller.data.jk_acb.armature
                    # and subscribe the mode change callback on both armatures...
                    _functions_.subscribe_mode_to(controller, _functions_.armature_mode_callback)
                    _functions_.subscribe_mode_to(deformer, _functions_.armature_mode_callback)
            # get a ref to the deformer... (might be None if adding for the first time)
            deformer = controller.data.jk_acb.armature
            # if we are orienting controls, orient them...
            if self.orient:
                _functions_.set_control_orientation(controller, bones)
            # if we are parenting deforms, parent them...
            if self.parent:
                _functions_.set_deform_parenting(controller, deformer, bones)
        # if we are removing deform bones...
        elif self.action == 'REMOVE':
            # if we are removing only selected or deforming bones...
            if self.only_deforms or self.only_selected or controller.data.jk_acb.use_combined:
                deform_bones = _functions_.remove_deform_bones(controller, deformer, bones)
                controller.data.jk_acb.deforms = json.dumps(deform_bones)
            else:
                # otherwise just remove the deform armature...
                _functions_.remove_deform_armature(controller)
        # if we are updating them...
        elif self.action == 'UPDATE':
            # perform and save the initial update...
            deform_bones = _functions_.update_deform_bones(controller, deformer)
            controller.data.jk_acb.deforms = json.dumps(deform_bones)
            # if we are orienting controls, orient them...
            if self.orient:
                _functions_.set_control_orientation(controller, bones)
            # if we are parenting deforms, parent them...
            if self.parent:
                _functions_.set_deform_parenting(controller, deformer, bones)
        # then always update the constraints and save any changes made to the deform bones...
        _functions_.set_deform_constraints(deformer, bones)
        deform_bones = _functions_.set_deform_bones(controller, deformer)
        controller.data.jk_acb.deforms = json.dumps(deform_bones)
        # turn auto update back on if it was on when we executed...
        controller.data.jk_acb.use_auto_update = is_auto_updating
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.orient = False
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "orient", icon='ORIENTATION_CURSOR')
        row.prop(self, "parent", icon='CON_CHILDOF')
        row.enabled = True if self.action in ['ADD', 'UPDATE'] else False
        row = layout.row()
        row.prop(self, "only_selected")
        row.prop(self, "only_deforms")

class JK_OT_Bake_Deforms(bpy.types.Operator):
    """Bakes the current deformation bones of the armature (all bones with "use_deform" set True)"""
    bl_idname = "jk.acb_bake_deforms"
    bl_label = "Bake Deforms"
    bl_options = {'REGISTER', 'UNDO'}

    armature: StringProperty(name="Armature", description="Name of the armature to bake", default="")

    bake_step: IntProperty(name="Bake Step", description="How often to evaluate keyframes when baking using 'Bake Deforms' to pre-bake keyframes", 
        default=1, min=1, options=set())

    only_active: BoolProperty(name="Only Active", description="Only bake the active action",
        default=False)

    visual_keys: BoolProperty(name="Visual Keying", description="Keyframe from the final transformation (with constraints applied)",
        default=True)

    curve_clean: BoolProperty(name="Clean Curves", description="After baking curves, remove redundant keys",
        default=False)

    fake_user: BoolProperty(name="Fake User", description="Save baked actions even if they have no users (stops them from being deleted on save/load)",
        default=True)

    def execute(self, context):
        prefs = bpy.context.preferences.addons["BLEND-ArmatureControlBones"].preferences
        armature = bpy.data.objects[self.armature]
        # we need have references to all the relevant armatures... (if using control/deforms)
        if armature.data.jk_acb.is_controller:
            controller, deformer = armature, armature.data.jk_acb.armature
        elif armature.data.jk_acb.is_deformer:
            controller, deformer = armature.data.jk_acb.armature, armature
        else:
            controller, deformer = armature, armature
        # get all the actions to bake... (and existing baked actions)
        sources, bakes = controller.data.jk_acb.get_actions(controller, self.only_active)
        # make sure we are in object mode...
        last_mode, last_selection = armature.mode, [o for o in bpy.context.selected_objects]
        if last_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # if we have auto keying enabled, turn it off... (just incase)
        is_auto_keying = bpy.context.scene.tool_settings.use_keyframe_insert_auto
        if is_auto_keying:
            bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
        # set our meshes to use deforms... (if there are deform bones)
        if controller.data.jk_acb.is_controller:
            if not controller.data.jk_acb.use_deforms:
                controller.data.jk_acb.use_deforms = True
            if controller.data.jk_acb.hide_deforms:
                controller.data.jk_acb.hide_deforms = False
        # deselect all objects and select only the deform armature...
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = deformer
        deformer.select_set(True)
        # if the deformer doesn't have animation data, create it...
        if not deformer.animation_data:
            deformer.animation_data_create()
        # jump into pose mode...
        bpy.ops.object.mode_set(mode='POSE')
        # make sure only deforming bones are selected...
        for pb in deformer.pose.bones:
            pb.bone.select = pb.bone.use_deform
        # for each action...
        for source, baked in sources.items():
            # set it to the active action...
            controller.animation_data.action = source
            # clear the controllers pose transforms... (does baking already do this?)
            for pb in controller.pose.bones:
                pb.location, pb.scale, pb.rotation_euler = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]
                pb.rotation_quaternion, pb.rotation_axis_angle = [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]
            # bake the action...
            bpy.ops.nla.bake(frame_start=int(round(source.frame_range[0], 0)), frame_end=int(round(source.frame_range[1], 0)),
                step=self.bake_step, only_selected=True, visual_keying=self.visual_keys, clear_constraints=False, clear_parents=False, 
                use_current_action=False, clean_curves=self.curve_clean, bake_types={'POSE'})
            # remove the old action if there is one...
            if baked:
                bpy.data.actions.remove(baked)
            # and name the new one, setting fake user as required...
            deformer.animation_data.action.name = prefs.deform_prefix + source.name
            deformer.animation_data.action.use_fake_user = self.fake_user
        # and mute the deform constraints so we can preview the animations... (if there are deform bones)
        if controller.data.jk_acb.is_controller:
            _functions_.mute_deform_constraints(deformer, True)
        # and switch auto keying back on if it got turned off...
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = is_auto_keying
        bpy.ops.object.mode_set(mode=last_mode)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.orient = False
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "bake_step")
        row.prop(self, "fake_user", text="", icon='FAKE_USER_ON' if self.fake_user else 'FAKE_USER_OFF')
        row = layout.row()
        row.prop(self, "only_active")
        row.prop(self, "visual_keys")
        row.prop(self, "curve_clean")

class JK_OT_Bake_Controls(bpy.types.Operator):
    """Bakes the current control bones of the armature (all bones without "use_deform" set True)"""
    bl_idname = "jk.acb_bake_controls"
    bl_label = "Bake Controls"
    bl_options = {'REGISTER', 'UNDO'}

    armature: StringProperty(name="Armature", description="Name of the armature to bake", default="")

    bake_step: IntProperty(name="Bake Step", description="How often to evaluate keyframes when baking using 'Bake Deforms' to pre-bake keyframes", 
        default=1, min=1, options=set())

    only_active: BoolProperty(name="Only Active", description="Only bake the active action",
        default=False)

    visual_keys: BoolProperty(name="Visual Keying", description="Keyframe from the final transformation (with constraints applied)",
        default=True)

    curve_clean: BoolProperty(name="Clean Curves", description="After baking curves, remove redundant keys",
        default=False)

    fake_user: BoolProperty(name="Fake User", description="Save baked actions even if they have no users (stops them from being deleted on save/load)",
        default=True)

    def execute(self, context):
        prefs = bpy.context.preferences.addons["BLEND-ArmatureControlBones"].preferences
        armature = bpy.data.objects[self.armature]
        # we need to have references to all the relevant armatures... (if using control/deforms)
        if armature.data.jk_acb.is_controller:
            controller, deformer = armature, armature.data.jk_acb.armature
        elif armature.data.jk_acb.is_deformer:
            controller, deformer = armature.data.jk_acb.armature, armature
        else:
            controller, deformer = armature, armature
        # get all the actions to bake... (and existing baked actions)
        sources, bakes = deformer.data.jk_acb.get_actions(deformer, self.only_active, reverse=True)
        # make sure we are in object mode...
        last_mode, last_selection = armature.mode, [o for o in bpy.context.selected_objects]
        if last_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # if we have auto keying enabled, turn it off... (just incase)
        is_auto_keying = bpy.context.scene.tool_settings.use_keyframe_insert_auto
        if is_auto_keying:
            bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
        # set our meshes to use deforms... (if there are deform bones)
        if controller.data.jk_acb.is_controller:
            if not controller.data.jk_acb.use_deforms:
                controller.data.jk_acb.use_deforms = True
            if controller.data.jk_acb.hide_deforms:
                controller.data.jk_acb.hide_deforms = False
        # deselect all objects and select only the control armature...
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = controller
        controller.select_set(True)
        # if the deformer doesn't have animation data, create it...
        if not controller.animation_data:
            controller.animation_data_create()
        # jump into pose mode...
        bpy.ops.object.mode_set(mode='POSE')
        # make sure only non deforming bones are selected...
        for pb in controller.pose.bones:
            pb.bone.select = not pb.bone.use_deform
        # for each action...
        for baked, source in bakes.items():
            # set it to the active action...
            deformer.animation_data.action = baked
            # clear the deformers pose transforms... (does baking already do this?)
            for pb in deformer.pose.bones:
                pb.location, pb.scale, pb.rotation_euler = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]
                pb.rotation_quaternion, pb.rotation_axis_angle = [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]
            # bake the action...
            bpy.ops.nla.bake(frame_start=int(round(baked.frame_range[0], 0)), frame_end=int(round(baked.frame_range[1], 0)),
                step=self.bake_step, only_selected=True, visual_keying=self.visual_keys, clear_constraints=False, clear_parents=False, 
                use_current_action=False, clean_curves=self.curve_clean, bake_types={'POSE'})
            # remove the old action if there is one...
            if source:
                bpy.data.actions.remove(source)
            # and name the new one, setting fake user as required...
            controller.animation_data.action.name = baked.name[len(prefs.deform_prefix):]
            controller.animation_data.action.use_fake_user = self.fake_user
        # and mute the deform constraints so we can preview the animations... (if there are deform bones)
        if controller.data.jk_acb.is_controller:
            _functions_.mute_deform_constraints(deformer, True)
        # and switch auto keying back on if it got turned off...
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = is_auto_keying
        bpy.ops.object.mode_set(mode=last_mode)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.orient = False
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "bake_step")
        row.prop(self, "fake_user", text="", icon='FAKE_USER_ON' if self.fake_user else 'FAKE_USER_OFF')
        row = layout.row()
        row.prop(self, "only_active")
        row.prop(self, "visual_keys")
        row.prop(self, "curve_clean")

class JK_OT_Refresh_Constraints(bpy.types.Operator):
    """Refreshes the child of constraints used by control/deform bones after applying scale"""
    bl_idname = "jk.acb_refresh_constraints"
    bl_label = "Refresh Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        controller, deformer = _functions_.get_armatures()
        if controller:
            controller.data.jk_acb.apply_transforms(controller, deformer)
        return {'FINISHED'}
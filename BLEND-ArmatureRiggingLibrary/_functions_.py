import bpy
import json
import math
import mathutils

#------------------------------------------------------------------------------------------------------------------------------------------------------#

#----- GENERAL FUNCTIONS ------------------------------------------------------------------------------------------------------------------------------#

#------------------------------------------------------------------------------------------------------------------------------------------------------#

def get_active_bone(armature):
    bones = armature.data.edit_bones if armature.mode == 'EDIT' else armature.data.bones
    return bones.active

def set_active_bone(armature, bone):
    bones = armature.data.edit_bones if armature.mode == 'EDIT' else armature.data.bones
    bones.active = bone

def get_distance(start, end):
    x, y, z = end[0] - start[0], end[1] - start[1], end[2] - start[2]
    distance = math.sqrt((x)**2 + (y)**2 + (z)**2)
    return distance

def get_pole_angle(self):
    # this method is NOT working 100% of the time, and isn't necessery as poles are currently created along axes...
    armature = self.id_data
    bbs, rigging = armature.data.bones, armature.jk_arl.rigging[armature.jk_arl.active].opposable
    # if all the bone bones we need to calculate the pole angle exist...
    pole, owner, start = bbs.get(self.bone), bbs.get(rigging.bones[1].source), bbs.get(self.source)
    if pole and owner and start:
        # get what the pole normal and projected pole axis should be...
        pole_normal = (owner.tail_local - start.head_local).cross(pole.head_local - start.head_local)
        pole_axis = pole_normal.cross(start.tail_local - start.head_local)
        # calculate the angle, making it negative if needs to be...
        angle = start.x_axis.angle(pole_axis) * (-1 if start.x_axis.cross(pole_axis).angle(start.tail_local - start.head_local) < 1 else 1)
        return angle
    else:
        # if any bone bones didn't exsist just return 0.0... (they will exist if this function is being called though?)
        return 0.0
    #angle = -3.141593 if axis == 'X_NEGATIVE' else 1.570796 if axis == 'Z' else -1.570796 if axis == 'Z_NEGATIVE' else 0.0
    
def get_bone_side(name):
    n_up = name.upper()
    side = 'LEFT' if n_up.endswith(".L") or n_up.endswith("_L") else 'RIGHT' if n_up.endswith(".R") or n_up.endswith("_R") else 'NONE'
    return side

def get_bone_limb(name):
    limbs = {'ARM' : ["HUMERUS", "ULNA", "SHOULDER", "ELBOW", "WRIST"], 'LEG' : ["FEMUR", "TIBIA", "THIGH", "CALF", "KNEE", "ANKLE"],
    'DIGIT' : ["FINGER", "TOE", "THUMB", "INDEX", "MIDDLE", "RING", "LITTLE", "PINKY"], 'SPINE' : ["LUMBAR", "THORACIC", "CERVICAL", "VERTEBRA", "NECK", "HEAD"],
    'TAIL' : ["CAUDAL", "COCCYX"], 'WING' : ["CARPUS", "TIP"]}
    limb = 'ARM'
    for l, strings in limbs.items():
        if l in name.upper():
            limb = l
            break
        elif any(string in name.upper() for string in strings):
            limb = l
            break
    return limb

def get_chain_rigging(armature, filters={'OPPOSABLE' : True, 'PLANTIGRADE' : True}):
    chains = [r.opposable if r.flavour == 'OPPOSABLE' else r.plantigrade if r.flavour == 'PLANTIGRADE' else r.digitigrade
        for r in armature.jk_arl.rigging if r.flavour in filters]# and any(c.is_rigged for c in [r.opposable, r.plantigrade, r.digitigrade])]
    return chains

def get_chain_armatures():
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE' and len(get_chain_rigging(obj)) > 0]
    return armatures

def get_rigging_pointer(self):
    pointers = {'HEAD_HOLD' : self.headhold, 'TAIL_FOLLOW' : self.tailfollow, 
            'OPPOSABLE' : self.opposable, 'PLANTIGRADE' : self.plantigrade}
    return pointers[self.flavour]

def get_bone_string(armature, bone):
    string = 'bpy.data.objects["' + armature.name + '"].data.bones["' + bone.name + '"]'
    return string

#------------------------------------------------------------------------------------------------------------------------------------------------------#

#----- EDIT INTERFACE FUNCTIONS -----------------------------------------------------------------------------------------------------------------------#

#------------------------------------------------------------------------------------------------------------------------------------------------------#

def show_cosmetic_settings(box, pointer):
    row = box.row()
    row.prop(pointer, "use_default_shapes")
    row.prop(pointer, "use_default_groups")
    row.prop(pointer, "use_default_layers")

def show_twist_settings(layout, rigging, armature):
    twist, box = rigging.get_pointer(), layout.box()
    # show cosmetic settings and rigging flavour... 
    show_cosmetic_settings(box, twist)
    row = box.row()
    row.prop(rigging, "flavour")
    row = box.row()
    row.prop_search(twist.bone, "source", armature.data, "bones")
    row.prop(twist, "use_offset")
    row = box.row()
    row.prop_search(twist.constraints[0], "subtarget", armature.data, "bones")

def show_chain_settings(layout, rigging, armature):
    chain, box = rigging.get_pointer(), layout.box()
    # show cosmetic settings and rigging flavour... (and side if planti/digiti)
    show_cosmetic_settings(box, chain)
    row = box.row()
    row.prop(rigging, "flavour")
    if rigging.flavour in ['PLANTIGRADE', 'DIGITIGRADE']:
        row.prop(rigging, "side")
    # if this one of the chains with a pole...
    if rigging.flavour in ['OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE']:
        row = box.row()
        row.prop_search(chain.target, "source", armature.data, "bones", text="Source")
        # only plantigrade and digitigrade chains have a pivot...
        if rigging.flavour in ['PLANTIGRADE', 'DIGITIGRADE']:
            row = box.row()
            row.prop_search(chain.target, "pivot", armature.data, "bones", text="Pivot")
        row = box.row()
        row.prop(chain.pole, "axis", text="")
        row.prop(chain.pole, "distance", text="Pole Distance:")
        row.prop(chain, "use_floor")
        if chain.use_floor:
            row = box.row()
            row.prop_search(chain.floor, "root", armature.data, "bones", text="Floor Root")
            row.enabled = chain.is_rigged
        row = box.row()
        row.prop_search(chain.target, "root", armature.data, "bones", text="Target Root")
        row.enabled = chain.is_rigged
        row = box.row()
        row.prop_search(chain.pole, "root", armature.data, "bones", text="Pole Root")
        row.enabled = chain.is_rigged
    # else if this is a spline chain...
    elif rigging.flavour == 'SPLINE':
        row = box.row()
        row.prop_search(chain.spline, "end", armature.data, "bones", text="From")
        row.prop(chain.spline, "length")
        row = box.row()
        row.prop(chain.spline, "axis")
        row.prop(chain.spline, "distance")
        if chain.is_rigged:
            curve = bpy.data.objects[chain.spline.curve]
            row.prop(curve.data, "bevel_depth")
        else:
            row.prop(chain.spline, "bevel_depth")
        for i in range(len(chain.targets)):
            target, bone = chain.targets[i], chain.bones[i]
            row = box.row()
            row.label(text=target.source)
            col = row.column()
            col.prop(target, "use", text="Create Target")
            col.enabled = False if i == 0 or i == len(chain.targets) - 1 else True
            col = row.column()
            col.prop(bone, "axis", text="Shape Axis")
            col.enabled = chain.use_default_shapes
    # else if this is a tracking chain...
    elif rigging.flavour == 'TRACKING':
        row = box.row()
        row.prop_search(chain.target, "source", armature.data, "bones", text="From")
        row.prop(chain, "length")
        row = box.row()
        row.prop(chain.target, "axis")
        row.prop(chain.target, "distance")
        row = box.row()
        row.prop_search(chain.target, "root", armature.data, "bones", text="Target Root")
        row.enabled = chain.is_rigged
        for i in range(len(chain.bones)):
            bone = chain.bones[i]
            row = box.row()
            row.label(text=bone.source)
            col = row.column()
            col.prop(bone, "axis", text="Shape Axis")
            col.enabled = chain.use_default_shapes
    # else if this is a forward or scalar chain...
    elif rigging.flavour in ['SCALAR', 'FORWARD']:
        row = box.row()
        # both have the end and length properties...
        row.prop_search(chain.target, "end", armature.data, "bones", text="From")
        row.prop(chain.target, "length")
        # but only scalar chains can have floor bones...
        if rigging.flavour == 'SCALAR':
            row.prop(chain, "use_floor")
            if chain.use_floor:
                row = box.row()
                row.prop_search(chain.floor, "root", armature.data, "bones", text="Floor Root")
                row.enabled = chain.is_rigged
    

#------------------------------------------------------------------------------------------------------------------------------------------------------#

#----- POSE INTERFACE FUNCTIONS -----------------------------------------------------------------------------------------------------------------------#

#------------------------------------------------------------------------------------------------------------------------------------------------------#

def show_limit_rotation(box, limit_rot):
    # X row....
    x_row = box.row(align=True)
    col = x_row.column(align=True)
    col.prop(limit_rot, "use_limit_x", icon='CON_ROTLIMIT')
    col = x_row.column(align=True)
    col.prop(limit_rot, "min_x")
    col.enabled = limit_rot.use_limit_x
    col = x_row.column(align=True)
    col.prop(limit_rot, "max_x")
    col.enabled = limit_rot.use_limit_x
    # Y row...
    y_row = box.row(align=True)
    col = y_row.column(align=True)
    col.prop(limit_rot, "use_limit_y", icon='CON_ROTLIMIT')
    col = y_row.column(align=True)
    col.prop(limit_rot, "min_y")
    col.enabled = limit_rot.use_limit_x
    col = y_row.column(align=True)
    col.prop(limit_rot, "max_y")
    col.enabled = limit_rot.use_limit_x
    # Z row...
    z_row = box.row(align=True)
    col = z_row.column(align=True)
    col.prop(limit_rot, "use_limit_z", icon='CON_ROTLIMIT')
    col = z_row.column(align=True)
    col.prop(limit_rot, "min_z")
    col.enabled = limit_rot.use_limit_x
    col = z_row.column(align=True)
    col.prop(limit_rot, "max_z")
    col.enabled = limit_rot.use_limit_x
    # influence...
    row = box.row()
    row.prop(limit_rot, "influence")
    #row.prop(limit_rot, "owner_space")

def show_copy_constraints(box, pb, name, flavour=None):
    con = pb.constraints[name]
    row = box.row()
    row.label(text=name)
    row.prop(con, "influence")
    if con.influence > 0.0:
        row = box.row()
        row.prop(con, "use_x")
        row.prop(con, "use_y")
        row.prop(con, "use_z")

def show_bone_kinematics(box, pb, show_stretch=False):
    # if we want to display the IK stretching, show it...
    if show_stretch:
        row = box.row()
        row.prop(pb, "ik_stretch", icon='CON_STRETCHTO')
    # make a row for the columns...
    row = box.row()
    # lock column...
    lock_col = row.column(align=True)
    lock_col.prop(pb, "lock_ik_x", text="X", emboss=False)
    lock_col.prop(pb, "lock_ik_y", text="Y", emboss=False)
    lock_col.prop(pb, "lock_ik_z", text="Z", emboss=False)
    # stiffness column...
    stiff_col = row.column(align=True)
    x_row = stiff_col.row(align=True)
    x_row.prop(pb, "ik_stiffness_x", text="")
    x_row.prop(pb, "use_ik_limit_x", text="", icon='CON_ROTLIMIT')
    x_row.active = not pb.lock_ik_x
    y_row = stiff_col.row(align=True)
    y_row.prop(pb, "ik_stiffness_y", text="")
    y_row.prop(pb, "use_ik_limit_y", text="", icon='CON_ROTLIMIT')
    y_row.active = not pb.lock_ik_y
    z_row = stiff_col.row(align=True)
    z_row.prop(pb, "ik_stiffness_z", text="")
    z_row.prop(pb, "use_ik_limit_z", text="", icon='CON_ROTLIMIT')
    z_row.active = not pb.lock_ik_z
    # limit column...
    limit_col = row.column(align=True)
    x_row = limit_col.row(align=True)
    x_row.prop(pb, "ik_min_x", text="")
    x_row.prop(pb, "ik_max_x", text="")
    x_row.active = pb.use_ik_limit_x and not pb.lock_ik_x
    y_row = limit_col.row(align=True)
    y_row.prop(pb, "ik_min_y", text="")
    y_row.prop(pb, "ik_max_y", text="")
    y_row.active = pb.use_ik_limit_y and not pb.lock_ik_y
    z_row = limit_col.row(align=True)
    z_row.prop(pb, "ik_min_z", text="")
    z_row.prop(pb, "ik_max_z", text="")
    z_row.active = pb.use_ik_limit_z and not pb.lock_ik_z

def show_track_kinematics(box, pb, bone):
    # make a row for the columns...
    row = box.row()
    con_col = row.column(align=True)
    con_col.ui_units_x = 20
    lean_row = con_col.row(align=True)
    lean_row.prop(bone, "lean")
    turn_row = con_col.row(align=True)
    turn_row.prop(bone, "turn")
    stretch_row = con_col.row(align=True)
    stretch_row.prop(pb, "ik_stretch", text="Stretch")
    # limit column...
    limit_col = row.column(align=True)
    x_row = limit_col.row(align=True)
    x_row.prop(pb, "ik_stiffness_x", text="X")
    x_row.prop(pb, "ik_min_x", text="")
    x_row.prop(pb, "ik_max_x", text="")
    y_row = limit_col.row(align=True)
    y_row.prop(pb, "ik_stiffness_y", text="Y")
    y_row.prop(pb, "ik_min_y", text="")
    y_row.prop(pb, "ik_max_y", text="")
    z_row = limit_col.row(align=True)
    z_row.prop(pb, "ik_stiffness_z", text="Z")
    z_row.prop(pb, "ik_min_z", text="")
    z_row.prop(pb, "ik_max_z", text="")

def show_soft_kinematics(box, pb, copy, limit):
    row = box.row()
    row.label(text="Inverse Kinematics: " + pb.name)
    # show the bones IK stretching, copy scale power and limit scale Y limit...
    row = box.row(align=True)
    # all in one row...
    row.prop(pb, "ik_stretch", text="Stretch", icon='CON_STRETCHTO')
    row.prop(copy, "power", text="Power", icon='CON_SIZELIKE')
    row.prop(limit, "max_y", text="Max Y", icon='CON_SIZELIMIT')

def show_twist_controls(layout, rigging, armature):
    pbs, twist = armature.pose.bones, rigging.get_pointer()
    pb, box = pbs.get(twist.bone.source), layout.box()
    if pb and twist.is_rigged and twist.has_properties:
        if rigging.flavour == 'HEAD_HOLD':
            damp_track, limit_rot = pb.constraints.get("TWIST - Damped Track"), pb.constraints.get("TWIST - Limit Rotation")
            show_limit_rotation(box, limit_rot)
        elif rigging.flavour == 'TAIL_FOLLOW':
            show_bone_kinematics(box, pb, show_stretch=False)
    else:
        box.label(text="Animation controls appear here once rigged...")

def show_chain_controls(layout, rigging, armature):
    pbs, chain = armature.pose.bones, rigging.get_pointer()
    box = layout.box()
    if chain.is_rigged and chain.has_properties:
        # show the IK/FK switching properties... (on chains with switching)
        if rigging.flavour in ['OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE']:
            row = box.row()
            row.prop(chain, "use_auto_fk")
            row.prop(chain, "use_fk")
            row = box.row()
            row.prop(chain, "ik_softness")
            row.prop(chain, "fk_influence")
            row.enabled = not chain.use_fk
        # spline chains have the fit curve property...
        elif rigging.flavour == 'SPLINE':
            row = box.row()
            row.prop(chain, "fit_curve")
        # scalar chains only have IK softness... (for now)
        elif rigging.flavour == 'SCALAR':
            row = box.row()
            row.prop(chain, "ik_softness")
         # else if this is a tracking chain...
        elif rigging.flavour == 'TRACKING':
            row = box.row()
            control_pb = pbs.get(chain.target.control)
            if control_pb:
                lock_x = control_pb.constraints.get("LOCK X - Locked Track")
                lock_z = control_pb.constraints.get("LOCK Z - Locked Track")
                if lock_x and lock_z:
                    x_col = row.column(align=True)
                    x_row = x_col.row(align=True)
                    mute_col = x_row.column(align=True)
                    mute_col.prop(lock_x, "mute", text="Lock X")
                    inf_col = x_row.column(align=True)
                    inf_col.prop(lock_x, "influence")
                    inf_col.enabled = not lock_x.mute

                    z_col = row.column(align=True)
                    z_row = z_col.row(align=True)
                    mute_col = z_row.column(align=True)
                    mute_col.prop(lock_z, "mute", text="Lock Z")
                    inf_col = z_row.column(align=True)
                    inf_col.prop(lock_z, "influence")
                    inf_col.enabled = not lock_z.mute
            
            box = layout.box()
            for bone in chain.bones:
                source_pb = pbs.get(bone.source)
                row = box.row()
                row.label(text="Tracking: " + bone.source)
                if source_pb:
                    copy = source_pb.constraints.get('TRACK - Copy Rotation')
                    if copy:
                        row = box.row()
                        row.prop(copy, "influence")
                show_track_kinematics(box, source_pb, bone)
        # if the chain has soft IK display the bone kinematics...
        if rigging.flavour in ['OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE', 'SCALAR']:
            box = layout.box()
            for bone in chain.bones:
                source_pb, gizmo_pb = pbs.get(bone.source), pbs.get(bone.gizmo)
                if source_pb and gizmo_pb:
                    copy, limit = gizmo_pb.constraints.get("SOFT - Copy Scale"), gizmo_pb.constraints.get("SOFT - Limit Scale")
                    if copy and limit:
                        show_soft_kinematics(box, source_pb, copy, limit)
                    show_bone_kinematics(box, source_pb, show_stretch=False)

        elif rigging.flavour == 'FORWARD':
            for bone in chain.bones:
                source_pb = pbs.get(bone.source)
                box.label(text=bone.source)
                for name in ["FORWARD - Copy Location", "FORWARD - Copy Rotation", "FORWARD - Copy Scale"]: 
                    if name in source_pb.constraints:
                        show_copy_constraints(box, source_pb, name)




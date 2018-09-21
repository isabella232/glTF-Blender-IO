"""
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * Contributor(s): Julien Duroure.
 *
 * ***** END GPL LICENSE BLOCK *****
 """


import bpy
from mathutils import Vector, Matrix, Quaternion
from ..com.gltf2_blender_conversion import *
from ..com.gltf2_blender_utils import *

class BlenderSkin():

    @staticmethod
    def create_armature(pyskin, parent):

        pyskin.blender_armature_name = None

        if pyskin.name is not None:
            name = pyskin.name
        else:
            name = "Armature_" + str(pyskin.index)

        armature = bpy.data.armatures.new(name)
        obj = bpy.data.objects.new(name, armature)
        obj.show_x_ray = True
        # obj.draw_type = 'WIRE'
        bpy.data.scenes[pyskin.gltf.blender_scene].objects.link(obj)
        pyskin.blender_armature_name = obj.name
        if parent and parent in pyskin.gltf.scene.nodes:
            obj.parent = bpy.data.objects[pyskin.gltf.scene.nodes[parent].blender_object]


    @staticmethod
    def set_bone_transforms(pyskin, bone, node, parent):
        obj   = bpy.data.objects[pyskin.blender_armature_name]
        
        # Set bone bind_pose by inverting bindpose matrix
        if node.index in pyskin.bones:
            index_in_skel = pyskin.bones.index(node.index)
            # Needed to keep scale in matrix, as bone.matrix seems to drop it
            if index_in_skel < len(pyskin.data):
                node.blender_bone_matrix = Conversion.matrix_gltf_to_blender(pyskin.data[index_in_skel]).inverted()
                bone.matrix = node.blender_bone_matrix
            else:
                pyskin.gltf.log.error("Error with inverseBindMatrix for skin " + pyskin)
        else:
            print('No invBindMatrix for bone ' + str(node.index))
            node.blender_bone_matrix = Matrix()

        # Parent the bone
        if parent is not None and hasattr(pyskin.gltf.scene.nodes[parent], "blender_bone_name"):
            bone.parent = obj.data.edit_bones[pyskin.gltf.scene.nodes[parent].blender_bone_name] #TODO if in another scene

        # Switch to Pose mode
        bpy.ops.object.mode_set(mode="POSE")
        obj.data.pose_position = 'POSE'
        bpy.context.scene.update()

        # Set posebone location/rotation/scale (in armature space)
        # location is actual bone location minus it's original (bind) location
        location, rotation, scale  = Conversion.matrix_gltf_to_blender(node.transform).decompose()
        if parent is not None and hasattr(pyskin.gltf.scene.nodes[parent], "blender_bone_matrix"):
            parent_mat = pyskin.gltf.scene.nodes[parent].blender_bone_matrix

            # Get armature space location (bindpose + pose)
            transform_location = Matrix.Translation(location)
            arm_space_location = Utils.get_armspace_trans(transform_location, parent_mat)

            # Remove original bind location from armspace location
            inv_arm_space_bind_location = Matrix.Translation(node.blender_bone_matrix.to_translation()).inverted()
            final_location = inv_arm_space_bind_location * arm_space_location
            obj.pose.bones[node.blender_bone_name].location = node.blender_bone_matrix.to_quaternion().inverted().to_matrix().to_4x4() * final_location
            # Do the same for rotation
            transform_rotation = rotation.to_matrix().to_4x4()
            arm_space_rotation = Utils.get_armspace_quat(transform_rotation, parent_mat)
            obj.pose.bones[node.blender_bone_name].rotation_quaternion = node.blender_bone_matrix.to_quaternion().inverted() * arm_space_rotation

            transform_scale = Utils.scale_to_matrix(scale)
            arm_space_scale = Utils.get_armspace_scale(transform_scale, parent_mat)
            obj.pose.bones[node.blender_bone_name].scale = Utils.scale_to_matrix(node.blender_bone_matrix.to_scale()).inverted() * arm_space_scale
        else:
            obj.pose.bones[node.blender_bone_name].location = Matrix.Translation(node.blender_bone_matrix.to_translation()).inverted() * location
            obj.pose.bones[node.blender_bone_name].rotation_quaternion = node.blender_bone_matrix.to_quaternion().inverted() * rotation
            obj.pose.bones[node.blender_bone_name].scale = scale

    @staticmethod
    def create_bone(pyskin, node, parent):
        scene = bpy.data.scenes[pyskin.gltf.blender_scene]
        obj   = bpy.data.objects[pyskin.blender_armature_name]

        bpy.context.screen.scene = scene
        scene.objects.active = obj
        obj.data.pose_position = 'REST'
        bpy.ops.object.mode_set(mode="EDIT")

        if node.name:
            name = node.name
        else:
            name = "Bone_" + str(node.index)

        bone = obj.data.edit_bones.new(name)
        node.blender_bone_name = bone.name
        node.blender_armature_name = pyskin.blender_armature_name
        bone.tail = Vector((0.0,1.0,0.0)) # Needed to keep bone alive

        # set bind and pose transforms
        BlenderSkin.set_bone_transforms(pyskin, bone, node, parent)

        bpy.ops.object.mode_set(mode="OBJECT")

    @staticmethod
    def create_vertex_groups(pyskin):
        for mesh in pyskin.mesh_id:
            obj = bpy.data.objects[pyskin.gltf.scene.nodes[mesh].blender_object]
            for bone in pyskin.bones:
                obj.vertex_groups.new(pyskin.gltf.scene.nodes[bone].blender_bone_name)

    @staticmethod
    def assign_vertex_groups(pyskin):
        for mesh in pyskin.mesh_id:
            node = pyskin.gltf.scene.nodes[mesh]
            obj = bpy.data.objects[node.blender_object]

            offset = 0
            for prim in node.mesh.primitives:
                idx_already_done = {}

                if 'JOINTS_0' in prim.attributes.keys() and 'WEIGHTS_0' in prim.attributes.keys():
                    joint_ = prim.attributes['JOINTS_0']['result']
                    weight_ = prim.attributes['WEIGHTS_0']['result']

                    for poly in obj.data.polygons:
                        for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                            vert_idx = obj.data.loops[loop_idx].vertex_index

                            if vert_idx in idx_already_done.keys():
                                continue
                            idx_already_done[vert_idx] = True

                            if vert_idx in range(offset, offset + prim.vertices_length):

                                tab_index = vert_idx - offset
                                cpt = 0
                                for joint_idx in joint_[tab_index]:
                                    weight_val = weight_[tab_index][cpt]
                                    if weight_val != 0.0:   # It can be a problem to assign weights of 0
                                                            # for bone index 0, if there is always 4 indices in joint_ tuple
                                        group = obj.vertex_groups[pyskin.gltf.scene.nodes[pyskin.bones[joint_idx]].blender_bone_name]
                                        group.add([vert_idx], weight_val, 'REPLACE')
                                    cpt += 1
                else:
                    pyskin.gltf.log.error("No Skinning ?????") #TODO


            offset = offset + prim.vertices_length

    @staticmethod
    def create_armature_modifiers(pyskin):
        for meshid in pyskin.mesh_id:
            node = pyskin.gltf.scene.nodes[meshid]
            obj = bpy.data.objects[node.blender_object]

            for obj_sel in bpy.context.scene.objects:
                obj_sel.select = False
            obj.select = True
            bpy.context.scene.objects.active = obj

            #bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            #obj.parent = bpy.data.objects[pyskin.blender_armature_name]
            arma = obj.modifiers.new(name="Armature", type="ARMATURE")
            arma.object = bpy.data.objects[pyskin.blender_armature_name]



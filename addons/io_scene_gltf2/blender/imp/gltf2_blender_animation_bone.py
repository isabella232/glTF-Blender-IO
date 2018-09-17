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
from mathutils import Quaternion, Matrix

from .gltf2_blender_animation_data import *
from ..com.gltf2_blender_conversion import *
from ..com.gltf2_blender_utils import *

class BlenderBoneAnim():

    @staticmethod
    def anim(pyanim):
        obj   = bpy.data.objects[pyanim.animation.gltf.skins[pyanim.animation.node.skin_id].blender_armature_name]
        bone  = obj.pose.bones[pyanim.animation.node.blender_bone_name]
        fps = bpy.context.scene.render.fps

        for anim in pyanim.animation.anims.keys():
            if pyanim.animation.gltf.animations[anim].name:
                name = pyanim.animation.gltf.animations[anim].name + "_" + obj.name
            else:
                name = "Animation_" + str(pyanim.animation.gltf.animations[anim].index) + "_" + obj.name
            if name not in bpy.data.actions:
                action = bpy.data.actions.new(name)
            else:
                action = bpy.data.actions[name]
            if not obj.animation_data:
                obj.animation_data_create()
            obj.animation_data.action = bpy.data.actions[action.name]

            for channel in pyanim.animation.anims[anim]:
                if channel.path == "translation":
                    blender_path = "location"
                    for key in channel.data:
                        transform = Matrix.Translation(Conversion.loc_gltf_to_blender(list(key[1])))
                        if not pyanim.animation.node.parent:
                            mat = transform
                        else:
                            if not pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].is_joint: # TODO if Node in another scene
                                parent_mat = bpy.data.objects[pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_object].matrix_world
                                mat = transform
                            else:
                                parent_mat = pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_bone_matrix
                                scale = Utils.scale_to_matrix(parent_mat.to_scale())
                                mat = (parent_mat.to_quaternion() * transform.to_quaternion()).to_matrix().to_4x4()
                                mat = scale * Matrix.Translation(parent_mat.to_translation() + ( parent_mat.to_quaternion() * transform.to_translation() )) * mat
                                # mat = Matrix.Translation(Utils.get_armspace_trans(transform, parent_mat))
                                #TODO scaling of bones ?

                        final_trans = Utils.get_armspace_trans(transform, parent_mat)
                        trans_mat = Matrix.Translation(pyanim.animation.node.blender_bone_matrix.to_translation()).inverted()
                        bone.location = trans_mat * final_trans  
                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='location')


                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "location"]:
                        for kf in fcurve.keyframe_points:
                            BlenderAnimationData.set_interpolation(channel.interpolation, kf)

                elif channel.path == "rotation":
                    blender_path = "rotation_quaternion"
                    for key in channel.data:
                        transform = (Conversion.quaternion_gltf_to_blender(key[1])).to_matrix().to_4x4()
                        if not pyanim.animation.node.parent:
                            mat = transform
                            bone.rotation_quaternion = pyanim.animation.node.blender_bone_matrix.to_quaternion().inverted() * mat.to_quaternion()
                        else:
                            if not pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].is_joint: # TODO if Node in another scene
                                parent_mat = bpy.data.objects[pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_object].matrix_world
                                mat = transform
                                bone.rotation_quaternion = pyanim.animation.node.blender_bone_matrix.to_quaternion().inverted() * mat.to_quaternion()
                            else:
                                parent_mat = pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_bone_matrix

                                mat = (parent_mat.to_quaternion() * transform.to_quaternion()).to_matrix().to_4x4()
                                mat = Matrix.Translation(parent_mat.to_translation() + ( parent_mat.to_quaternion() * transform.to_translation() )) * mat
                                #TODO scaling of bones ?
                                final_rot = Utils.get_armspace_quat(transform, parent_mat)
                                bone.rotation_quaternion = pyanim.animation.node.blender_bone_matrix.to_quaternion().inverted() * final_rot

                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='rotation')

                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "rotation"]:
                        for kf in fcurve.keyframe_points:
                            BlenderAnimationData.set_interpolation(channel.interpolation, kf)


                elif channel.path == "scale":
                    blender_path = "scale"
                    for key in channel.data:
                        s = Conversion.scale_gltf_to_blender(list(key[1]))
                        transform = Matrix([
                            [s[0], 0, 0, 0],
                            [0, s[1], 0, 0],
                            [0, 0, s[2], 0],
                            [0, 0, 0, 1]
                        ])

                        if not pyanim.animation.node.parent:
                            mat = transform
                        else:
                            if not pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].is_joint: # TODO if Node in another scene
                                parent_mat = bpy.data.objects[pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_object].matrix_world
                                mat = transform
                            else:
                                parent_mat = pyanim.animation.gltf.scene.nodes[pyanim.animation.node.parent].blender_bone_matrix
                                mat = parent_mat.inverted() * transform



                        #bone.scale # TODO
                        final_scale = Utils.get_armspace_scale(transform, parent_mat)
                        bone.scale = final_scale
                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='scale')

                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "scale"]:
                        for kf in fcurve.keyframe_points:
                            BlenderAnimationData.set_interpolation(channel.interpolation, kf)

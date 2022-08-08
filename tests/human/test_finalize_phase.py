from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.tests.fixtures import context
from HumGen3D.tests.fixtures import finalize_phase_human as human


def test_revert(human, context):
    human.finalize_phase.revert(context)
    assert human.phase == "creation"


def test_backup_rig(human, context):
    rig = human.finalize_phase.backup_rig
    assert rig in context.scene.objects
    assert rig.type == "ARMATURE"


def test_backup_rig(human, context):
    rig = human.finalize_phase.backup_rig
    assert context.scene.objects.get(rig.name)
    assert rig.type == "ARMATURE"

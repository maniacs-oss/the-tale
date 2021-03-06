# coding: utf-8
import random

from dext.common.utils import discovering

from rels import Column
from rels.django import DjangoEnum

from the_tale.amqp_environment import environment

from the_tale.common.postponed_tasks.prototypes import PostponedTaskPrototype
from the_tale.common.utils.logic import random_value_by_priority

from the_tale.accounts.prototypes import AccountPrototype

from the_tale.game.balance.power import Power

from the_tale.game.cards import relations

from the_tale.game.places import storage as places_storage
from the_tale.game.places import logic as places_logic

from the_tale.game.persons import storage as persons_storage
from the_tale.game.persons import logic as persons_logic

from the_tale.game.balance import constants as c
from the_tale.game.prototypes import TimePrototype

from the_tale.game.relations import HABIT_TYPE
from the_tale.game.heroes.relations import PREFERENCE_TYPE, ITEMS_OF_EXPENDITURE

from the_tale.game.artifacts.storage import artifacts_storage
from the_tale.game.artifacts import relations as artifacts_relations

from the_tale.game.companions import relations as companions_relations
from the_tale.game.companions import storage as companions_storage
from the_tale.game.companions import logic as companions_logic

from the_tale.game.cards.postponed_tasks import UseCardTask
from the_tale.game.cards import objects


class BaseEffect(object):
    TYPE = None

    def activate(self, hero, card_uid, data):
        data['hero_id'] = hero.id
        data['account_id'] = hero.account_id
        data['card_uid'] = card_uid

        card_task = UseCardTask(processor_id=self.TYPE.value,
                                hero_id=hero.id,
                                data=data)

        task = PostponedTaskPrototype.create(card_task)

        environment.workers.supervisor.cmd_logic_task(hero.account_id, task.id)

        return task


    def use(self, *argv, **kwargs):
        raise NotImplementedError()

    def check_hero_conditions(self, hero, data):
        return hero.cards.has_card(data['card_uid'])

    def hero_actions(self, hero, data):
        card = hero.cards.get_card(data['card_uid'])
        hero.cards.remove_card(card.uid)
        hero.statistics.change_cards_used(1)


    def create_card(self, available_for_auction):
        return objects.Card(type=self.TYPE, available_for_auction=available_for_auction)

    def name_for_card(self, card):
        return self.TYPE.text

    @classmethod
    def available(self):
        return True



class LevelUp(BaseEffect):
    TYPE = relations.CARD_TYPE.LEVEL_UP
    DESCRIPTION = 'Герой получает новый уровень. Накопленный опыт не сбрасывается.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        task.hero.increment_level(send_message=False)
        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)
        return task.logic_result()


class AddExperienceBase(BaseEffect):
    TYPE = None
    EXPERIENCE = None

    @property
    def DESCRIPTION(self):
        return 'Увеличивает опыт, который герой получит за выполнение текущего задания, на %(experience)d единиц.' % {'experience': self.EXPERIENCE}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not task.hero.quests.has_quests:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет задания.')

        task.hero.quests.current_quest.current_info.experience_bonus += self.EXPERIENCE
        task.hero.quests.mark_updated()

        return task.logic_result()

class AddExperienceCommon(AddExperienceBase):
    TYPE = relations.CARD_TYPE.ADD_EXPERIENCE_COMMON
    EXPERIENCE = 25

class AddExperienceUncommon(AddExperienceBase):
    TYPE = relations.CARD_TYPE.ADD_EXPERIENCE_UNCOMMON
    EXPERIENCE = AddExperienceCommon.EXPERIENCE * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddExperienceRare(AddExperienceBase):
    TYPE = relations.CARD_TYPE.ADD_EXPERIENCE_RARE
    EXPERIENCE = AddExperienceUncommon.EXPERIENCE * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddExperienceEpic(AddExperienceBase):
    TYPE = relations.CARD_TYPE.ADD_EXPERIENCE_EPIC
    EXPERIENCE = AddExperienceRare.EXPERIENCE * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddExperienceLegendary(AddExperienceBase):
    TYPE = relations.CARD_TYPE.ADD_EXPERIENCE_LEGENDARY
    EXPERIENCE = AddExperienceEpic.EXPERIENCE * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class AddPoliticPowerBase(BaseEffect):
    TYPE = None
    POWER = None

    @property
    def DESCRIPTION(self):
        return 'Увеличивает влияние, которое окажет герой после выполнения текущего задания, на %(power)d единиц.' % {'power': self.POWER}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not task.hero.quests.has_quests:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет задания')

        task.hero.quests.current_quest.current_info.power_bonus += self.POWER
        task.hero.quests.mark_updated()

        return task.logic_result()

class AddPoliticPowerCommon(AddPoliticPowerBase):
    TYPE = relations.CARD_TYPE.ADD_POWER_COMMON
    POWER = c.MINIMUM_CARD_POWER

class AddPoliticPowerUncommon(AddPoliticPowerBase):
    TYPE = relations.CARD_TYPE.ADD_POWER_UNCOMMON
    POWER = AddPoliticPowerCommon.POWER * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPoliticPowerRare(AddPoliticPowerBase):
    TYPE = relations.CARD_TYPE.ADD_POWER_RARE
    POWER = AddPoliticPowerUncommon.POWER * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPoliticPowerEpic(AddPoliticPowerBase):
    TYPE = relations.CARD_TYPE.ADD_POWER_EPIC
    POWER = AddPoliticPowerRare.POWER * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPoliticPowerLegendary(AddPoliticPowerBase):
    TYPE = relations.CARD_TYPE.ADD_POWER_LEGENDARY
    POWER = AddPoliticPowerEpic.POWER * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class AddBonusEnergyBase(BaseEffect):
    TYPE = None
    ENERGY = None

    @property
    def DESCRIPTION(self):
        return 'Вы получаете %(energy)d единиц дополнительной энергии.' % {'energy': self.ENERGY}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        task.hero.add_energy_bonus(self.ENERGY)
        return task.logic_result()

class AddBonusEnergyCommon(AddBonusEnergyBase):
    TYPE = relations.CARD_TYPE.ADD_BONUS_ENERGY_COMMON
    ENERGY = 10

class AddBonusEnergyUncommon(AddBonusEnergyBase):
    TYPE = relations.CARD_TYPE.ADD_BONUS_ENERGY_UNCOMMON
    ENERGY = AddBonusEnergyCommon.ENERGY * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddBonusEnergyRare(AddBonusEnergyBase):
    TYPE = relations.CARD_TYPE.ADD_BONUS_ENERGY_RARE
    ENERGY = AddBonusEnergyUncommon.ENERGY * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddBonusEnergyEpic(AddBonusEnergyBase):
    TYPE = relations.CARD_TYPE.ADD_BONUS_ENERGY_EPIC
    ENERGY = AddBonusEnergyRare.ENERGY * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddBonusEnergyLegendary(AddBonusEnergyBase):
    TYPE = relations.CARD_TYPE.ADD_BONUS_ENERGY_LEGENDARY
    ENERGY = AddBonusEnergyEpic.ENERGY * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class AddGoldBase(BaseEffect):
    TYPE = None
    GOLD = None

    @property
    def DESCRIPTION(self):
        return 'Герой получает %(gold)d монет.' % {'gold': self.GOLD}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        from the_tale.game.heroes.relations import MONEY_SOURCE

        task.hero.change_money(MONEY_SOURCE.EARNED_FROM_HELP, self.GOLD)
        return task.logic_result()

class AddGoldCommon(AddGoldBase):
    TYPE = relations.CARD_TYPE.ADD_GOLD_COMMON
    GOLD = 1000

class AddGoldUncommon(AddGoldBase):
    TYPE = relations.CARD_TYPE.ADD_GOLD_UNCOMMON
    GOLD = AddGoldCommon.GOLD * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddGoldRare(AddGoldBase):
    TYPE = relations.CARD_TYPE.ADD_GOLD_RARE
    GOLD = AddGoldUncommon.GOLD * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class ChangeHabitBase(BaseEffect):
    TYPE = None
    HABIT = None
    POINTS = None

    @property
    def DESCRIPTION(self):
        if self.POINTS > 0:
            return 'Увеличивает %(habit)s героя на %(points)d единиц.' % {'habit': self.HABIT.text,
                                                                           'points': self.POINTS}
        return 'Уменьшает %(habit)s героя на %(points)d единиц.' % {'habit': self.HABIT.text,
                                                                     'points': -self.POINTS}

    @property
    def success_message(self):
        if self.POINTS > 0:
            return 'Увеличивает %(habit)s героя на %(points)d единиц.' % {'habit': self.HABIT.text,
                                                                           'points': self.POINTS}
        return 'Уменьшает %(habit)s героя на %(points)d единиц.' % {'habit': self.HABIT.text,
                                                                     'points': -self.POINTS}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        old_habits = (task.hero.habit_honor.raw_value, task.hero.habit_peacefulness.raw_value)

        task.hero.change_habits(self.HABIT, self.POINTS)

        if old_habits == (task.hero.habit_honor.raw_value, task.hero.habit_peacefulness.raw_value):
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Применение карты никак не изменит черты героя.')

        return task.logic_result()


class ChangeHabitHonorPlusUncommon(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_PLUS_UNCOMMON
    HABIT = HABIT_TYPE.HONOR
    POINTS = 25

class ChangeHabitHonorMinusUncommon(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_MINUS_UNCOMMON
    HABIT = HABIT_TYPE.HONOR
    POINTS = -25

class ChangeHabitPeacefulnessPlusUncommon(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_PLUS_UNCOMMON
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = 25

class ChangeHabitPeacefulnessMinusUncommon(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_MINUS_UNCOMMON
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = -25


class ChangeHabitHonorPlusRare(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_PLUS_RARE
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorPlusUncommon.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitHonorMinusRare(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_MINUS_RARE
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorMinusUncommon.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessPlusRare(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_PLUS_RARE
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessPlusUncommon.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessMinusRare(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_MINUS_RARE
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessMinusUncommon.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class ChangeHabitHonorPlusEpic(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_PLUS_EPIC
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorPlusRare.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitHonorMinusEpic(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_MINUS_EPIC
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorMinusRare.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessPlusEpic(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_PLUS_EPIC
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessPlusRare.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessMinusEpic(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_MINUS_EPIC
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessMinusRare.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class ChangeHabitHonorPlusLegendary(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_PLUS_LEGENDARY
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorPlusEpic.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitHonorMinusLegendary(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_HONOR_MINUS_LEGENDARY
    HABIT = HABIT_TYPE.HONOR
    POINTS = ChangeHabitHonorMinusEpic.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessPlusLegendary(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_PLUS_LEGENDARY
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessPlusEpic.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class ChangeHabitPeacefulnessMinusLegendary(ChangeHabitBase):
    TYPE = relations.CARD_TYPE.CHANGE_HABIT_PEACEFULNESS_MINUS_LEGENDARY
    HABIT = HABIT_TYPE.PEACEFULNESS
    POINTS = ChangeHabitPeacefulnessMinusEpic.POINTS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class PreferencesCooldownsResetBase(BaseEffect):
    TYPE = None
    PREFERENCE = None

    @property
    def DESCRIPTION(self):
        return 'Сбрасывает задержку на изменение предпочтения «%(preference)s».' % {'preference': self.PREFERENCE.text}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if not task.hero.preferences.is_available(self.PREFERENCE, account=AccountPrototype.get_by_id(task.hero.account_id)):
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Нельзя сбросить задержку на изменение предпочтения (предпочтение ещё не доступно герою).')

        task.hero.preferences.reset_change_time(self.PREFERENCE)
        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)
        return task.logic_result()


class PreferencesCooldownsResetMob(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_MOB
    PREFERENCE = PREFERENCE_TYPE.MOB

class PreferencesCooldownsResetPlace(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_PLACE
    PREFERENCE = PREFERENCE_TYPE.PLACE

class PreferencesCooldownsResetFriend(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_FRIEND
    PREFERENCE = PREFERENCE_TYPE.FRIEND

class PreferencesCooldownsResetEnemy(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_ENEMY
    PREFERENCE = PREFERENCE_TYPE.ENEMY

class PreferencesCooldownsResetEnergyRegeneration(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_ENERGY_REGENERATION
    PREFERENCE = PREFERENCE_TYPE.ENERGY_REGENERATION_TYPE

class PreferencesCooldownsResetEquipmentSlot(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_EQUIPMEN_SLOT
    PREFERENCE = PREFERENCE_TYPE.EQUIPMENT_SLOT

class PreferencesCooldownsResetRiskLevel(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_RISK_LEVEL
    PREFERENCE = PREFERENCE_TYPE.RISK_LEVEL

class PreferencesCooldownsResetCompanionDedication(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_COMPANION_DEDICATION
    PREFERENCE = PREFERENCE_TYPE.COMPANION_DEDICATION

class PreferencesCooldownsResetFavoriteItem(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_FAVORITE_ITEM
    PREFERENCE = PREFERENCE_TYPE.FAVORITE_ITEM

class PreferencesCooldownsResetArchetype(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_ARCHETYPE
    PREFERENCE = PREFERENCE_TYPE.ARCHETYPE

class PreferencesCooldownsResetCompanionEmpathy(PreferencesCooldownsResetBase):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_COMPANION_EMPATHY
    PREFERENCE = PREFERENCE_TYPE.COMPANION_EMPATHY


class PreferencesCooldownsResetAll(BaseEffect):
    TYPE = relations.CARD_TYPE.PREFERENCES_COOLDOWNS_RESET_ALL

    DESCRIPTION = 'Сбрасывает задержку на изменение всех предпочтений.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        for preference in PREFERENCE_TYPE.records:
            task.hero.preferences.reset_change_time(preference)
        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)
        return task.logic_result()


class ChangeAbilitiesChoices(BaseEffect):
    TYPE = relations.CARD_TYPE.CHANGE_ABILITIES_CHOICES
    DESCRIPTION = 'Изменяет список предлагаемых герою способностей (при выборе новой способности).'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not task.hero.abilities.rechooce_choices():
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Герой не может изменить выбор способностей (возможно, больше не из чего выбирать).')

        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)

        return task.logic_result()


class ResetAbilities(BaseEffect):
    TYPE = relations.CARD_TYPE.RESET_ABILITIES
    DESCRIPTION = 'Сбрасывает все способности героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if task.hero.abilities.is_initial_state():
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Способности героя уже сброшены.')

        task.hero.abilities.reset()

        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)

        return task.logic_result()


class ChangeItemOfExpenditureBase(BaseEffect):
    TYPE = None
    ITEM = None

    @property
    def DESCRIPTION(self):
        return 'Текущей целью трат героя становится %(item)s.' % {'item': self.ITEM.text}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if task.hero.next_spending == self.ITEM:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Герой уже копит деньги на эту цель.')

        if self.ITEM.is_HEAL_COMPANION and task.hero.companion is None:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет спутника, лечить некого.')

        task.hero.next_spending = self.ITEM
        task.hero.quests.mark_updated()
        return task.logic_result()

class ChangeHeroSpendingsToInstantHeal(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_INSTANT_HEAL
    ITEM = ITEMS_OF_EXPENDITURE.INSTANT_HEAL

class ChangeHeroSpendingsToBuyingArtifact(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_BUYING_ARTIFACT
    ITEM = ITEMS_OF_EXPENDITURE.BUYING_ARTIFACT

class ChangeHeroSpendingsToSharpeingArtifact(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_SHARPENING_ARTIFACT
    ITEM = ITEMS_OF_EXPENDITURE.SHARPENING_ARTIFACT

class ChangeHeroSpendingsToExperience(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_EXPERIENCE
    ITEM = ITEMS_OF_EXPENDITURE.EXPERIENCE

class ChangeHeroSpendingsToRepairingArtifact(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_REPAIRING_ARTIFACT
    ITEM = ITEMS_OF_EXPENDITURE.REPAIRING_ARTIFACT

class ChangeHeroSpendingsToHealCompanion(ChangeItemOfExpenditureBase):
    TYPE = relations.CARD_TYPE.CHANGE_HERO_SPENDINGS_TO_HEAL_COMPANION
    ITEM = ITEMS_OF_EXPENDITURE.HEAL_COMPANION


class RepairRandomArtifact(BaseEffect):
    TYPE = relations.CARD_TYPE.REPAIR_RANDOM_ARTIFACT
    DESCRIPTION = 'Чинит случайный артефакт из экипировки героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        choices = [item for item in list(task.hero.equipment.values()) if item.integrity < item.max_integrity]

        if not choices:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Экипировка не нуждается в ремонте.')

        artifact = random.choice(choices)

        artifact.repair_it()

        return task.logic_result(message='Целостность артефакта %(artifact)s полностью восстановлена.' % {'artifact': artifact.html_label()})


class RepairAllArtifacts(BaseEffect):
    TYPE = relations.CARD_TYPE.REPAIR_ALL_ARTIFACTS
    DESCRIPTION = 'Чинит все артефакты из экипировки героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not [item for item in list(task.hero.equipment.values()) if item.integrity < item.max_integrity]:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Экипировка не нуждается в ремонте.')

        for item in list(task.hero.equipment.values()):
            item.repair_it()

        return task.logic_result()


class CancelQuest(BaseEffect):
    TYPE = relations.CARD_TYPE.CANCEL_QUEST
    DESCRIPTION = 'Отменяет текущее задание героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not task.hero.quests.has_quests:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет задания.')

        task.hero.quests.pop_quest()
        task.hero.quests.mark_updated()

        return task.logic_result()


class GetArtifactBase(BaseEffect):
    TYPE = None
    DESCRIPTION = None

    class ARTIFACT_TYPE_CHOICES(DjangoEnum):
        priority = Column()
        rarity = Column(unique=False, single_type=False)

        records = ( ('LOOT', 0, 'лут', 1000, artifacts_relations.RARITY.NORMAL),
                    ('COMMON', 1, 'обычные', 100, artifacts_relations.RARITY.NORMAL),
                    ('RARE', 2, 'редкие', 10, artifacts_relations.RARITY.RARE),
                    ('EPIC', 3, 'эпические', 1, artifacts_relations.RARITY.EPIC), )

    INTERVAL = None

    def get_new_artifact_data(self):
        artifact_type = random_value_by_priority([(record, record.priority) for record in self.ARTIFACT_TYPE_CHOICES.records][-self.INTERVAL:])

        if artifact_type.is_LOOT:
            return artifacts_storage.loot, artifact_type.rarity

        return artifacts_storage.artifacts, artifact_type.rarity

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        artifacts_list, rarity = self.get_new_artifact_data()

        artifact = artifacts_storage.generate_artifact_from_list(artifacts_list, task.hero.level, rarity=rarity)

        task.hero.put_loot(artifact, force=True)

        task.hero.actions.request_replane()

        return task.logic_result(message='В рюкзаке героя появился новый артефакт: %(artifact)s' % {'artifact': artifact.html_label()})


class GetArtifactCommon(GetArtifactBase):
    TYPE = relations.CARD_TYPE.GET_ARTIFACT_COMMON
    DESCRIPTION = 'Герой получает случайный бесполезный предмет или артефакт.'
    INTERVAL = 4

class GetArtifactUncommon(GetArtifactBase):
    TYPE = relations.CARD_TYPE.GET_ARTIFACT_UNCOMMON
    DESCRIPTION = 'Герой получает случайный артефакт.'
    INTERVAL = 3

class GetArtifactRare(GetArtifactBase):
    TYPE = relations.CARD_TYPE.GET_ARTIFACT_RARE
    DESCRIPTION = 'Герой получает случайный редкий или эпический артефакт.'
    INTERVAL = 2

class GetArtifactEpic(GetArtifactBase):
    TYPE = relations.CARD_TYPE.GET_ARTIFACT_EPIC
    DESCRIPTION = 'Герой получает случайный эпический артефакт.'
    INTERVAL = 1


class InstantMonsterKill(BaseEffect):
    TYPE = relations.CARD_TYPE.INSTANT_MONSTER_KILL
    DESCRIPTION = 'Мгновенно убивает монстра, с которым сражается герой.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if not task.hero.actions.current_action.TYPE.is_BATTLE_PVE_1X1:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Герой ни с кем не сражается.')

        task.hero.actions.current_action.bit_mob(task.hero.actions.current_action.mob.max_health)

        return task.logic_result()



class KeepersGoodsBase(BaseEffect):
    TYPE = None
    GOODS = None

    @property
    def DESCRIPTION(self):
        return 'Создаёт в указанном городе %(goods)d «даров Хранителей». Город будет постепенно переводить их в продукцию, пока дары не кончатся.' % {'goods': self.GOODS}

    def use(self, task, storage, highlevel=None, **kwargs): # pylint: disable=R0911,W0613

        place_id = task.data.get('place_id')

        if place_id not in places_storage.places:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Город не найден.')

        if task.step.is_LOGIC:
            return task.logic_result(next_step=UseCardTask.STEP.HIGHLEVEL)

        elif task.step.is_HIGHLEVEL:
            place = places_storage.places[place_id]

            place.attrs.keepers_goods += self.GOODS
            place.refresh_attributes()

            places_logic.save_place(place)

            places_storage.places.update_version()

            return task.logic_result()


class KeepersGoodsCommon(KeepersGoodsBase):
    TYPE = relations.CARD_TYPE.KEEPERS_GOODS_COMMON
    GOODS = 20

class KeepersGoodsUncommon(KeepersGoodsBase):
    TYPE = relations.CARD_TYPE.KEEPERS_GOODS_UNCOMMON
    GOODS = KeepersGoodsCommon.GOODS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class KeepersGoodsRare(KeepersGoodsBase):
    TYPE = relations.CARD_TYPE.KEEPERS_GOODS_RARE
    GOODS = KeepersGoodsUncommon.GOODS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class KeepersGoodsEpic(KeepersGoodsBase):
    TYPE = relations.CARD_TYPE.KEEPERS_GOODS_EPIC
    GOODS = KeepersGoodsRare.GOODS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class KeepersGoodsLegendary(KeepersGoodsBase):
    TYPE = relations.CARD_TYPE.KEEPERS_GOODS_LEGENDARY
    GOODS = KeepersGoodsEpic.GOODS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)



class RepairBuilding(BaseEffect):
    TYPE = relations.CARD_TYPE.REPAIR_BUILDING

    DESCRIPTION = 'Полностью ремонтирует указанное строение.'

    def use(self, task, storage, highlevel=None, **kwargs): # pylint: disable=R0911,W0613

        building_id = task.data.get('building_id')

        if building_id not in places_storage.buildings:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Строение не найдено.')

        if task.step.is_LOGIC:
            return task.logic_result(next_step=UseCardTask.STEP.HIGHLEVEL)

        elif task.step.is_HIGHLEVEL:
            building = places_storage.buildings[building_id]

            while building.need_repair:
                building.repair()

            places_logic.save_building(building)

            return task.logic_result()



class AddPersonPowerBase(BaseEffect):
    TYPE = None
    BONUS = None

    @property
    def DESCRIPTION(self):
        if self.BONUS > 0:
            return 'Моментально увеличивает влияние Мастера на %(bonus)d единиц. Влияние засчитывается так, как если бы герой имел Мастера в предпочтении.' % {'bonus': self.BONUS}

        return 'Моментально уменьшает влияние Мастера на %(bonus)d единиц. Влияние засчитывается так, как если бы герой имел Мастера в предпочтении.' % {'bonus': -self.BONUS}

    @property
    def success_message(self):
        if self.BONUS > 0:
            return 'Влияние Мастера увеличено на %(bonus)d..' % {'bonus': self.BONUS}

        return 'Влияние Мастера уменьшено на %(bonus)d.' % {'bonus': -self.BONUS}


    def use(self, task, storage, highlevel=None, **kwargs): # pylint: disable=R0911,W0613

        person_id = task.data.get('person_id')

        if person_id not in persons_storage.persons:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Мастер не найден.')

        person = persons_storage.persons[person_id]

        if task.step.is_LOGIC:
            return task.logic_result(next_step=UseCardTask.STEP.HIGHLEVEL)

        elif task.step.is_HIGHLEVEL:

            person.politic_power.change_power(person=person,
                                              hero_id=task.hero_id,
                                              has_in_preferences=True,
                                              power=self.BONUS)
            persons_logic.save_person(person)
            persons_storage.persons.update_version()

            return task.logic_result()


class AddPersonPowerPositiveCommon(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_POSITIVE_COMMON
    BONUS = c.MINIMUM_CARD_POWER / 2

class AddPersonPowerPositiveUncommon(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_POSITIVE_UNCOMMON
    BONUS = AddPersonPowerPositiveCommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerPositiveRare(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_POSITIVE_RARE
    BONUS = AddPersonPowerPositiveUncommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerPositiveEpic(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_POSITIVE_EPIC
    BONUS = AddPersonPowerPositiveRare.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerPositiveLegendary(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_POSITIVE_LEGENDARY
    BONUS = AddPersonPowerPositiveEpic.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class AddPersonPowerNegativeCommon(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_NEGATIVE_COMMON
    BONUS = -c.MINIMUM_CARD_POWER / 2

class AddPersonPowerNegativeUncommon(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_NEGATIVE_UNCOMMON
    BONUS = AddPersonPowerNegativeCommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerNegativeRare(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_NEGATIVE_RARE
    BONUS = AddPersonPowerNegativeUncommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerNegativeEpic(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_NEGATIVE_EPIC
    BONUS = AddPersonPowerNegativeRare.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPersonPowerNegativeLegendary(AddPersonPowerBase):
    TYPE = relations.CARD_TYPE.ADD_PERSON_POWER_NEGATIVE_LEGENDARY
    BONUS = AddPersonPowerNegativeEpic.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)



class AddPlacePowerBase(BaseEffect):
    TYPE = None
    BONUS = None

    @property
    def DESCRIPTION(self):
        if self.BONUS > 0:
            return 'Моментально увеличивает влияние города на %(bonus)d единиц. Влияние засчитывается так, как если бы герой имел город в предпочтении.' % {'bonus': self.BONUS}

        return 'Моментально уменьшает влияние города на %(bonus)d единиц. Влияние засчитывается так, как если бы герой имел город в предпочтении.' % {'bonus': -self.BONUS}

    @property
    def success_message(self):
        if self.BONUS > 0:
            return 'Влияние города увеличено на %(bonus)d..' % {'bonus': self.BONUS}

        return 'Влияние города уменьшено на %(bonus)d.' % {'bonus': -self.BONUS}

    def use(self, task, storage, highlevel=None, **kwargs): # pylint: disable=R0911,W0613

        place_id = task.data.get('place_id')

        if place_id not in places_storage.places:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Город не найден.')

        if task.step.is_LOGIC:
            return task.logic_result(next_step=UseCardTask.STEP.HIGHLEVEL)

        elif task.step.is_HIGHLEVEL:
            place = places_storage.places[place_id]

            place.politic_power.change_power(place=place,
                                             hero_id=task.hero_id,
                                             has_in_preferences=True,
                                             power=self.BONUS)

            places_logic.save_place(place)
            places_storage.places.update_version()

            return task.logic_result()


class AddPlacePowerPositiveCommon(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_POSITIVE_COMMON
    BONUS = c.MINIMUM_CARD_POWER / 2

class AddPlacePowerPositiveUncommon(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_POSITIVE_UNCOMMON
    BONUS = AddPlacePowerPositiveCommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerPositiveRare(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_POSITIVE_RARE
    BONUS = AddPlacePowerPositiveUncommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerPositiveEpic(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_POSITIVE_EPIC
    BONUS = AddPlacePowerPositiveRare.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerPositiveLegendary(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_POSITIVE_LEGENDARY
    BONUS = AddPlacePowerPositiveEpic.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class AddPlacePowerNegativeCommon(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_NEGATIVE_COMMON
    BONUS = -c.MINIMUM_CARD_POWER / 2

class AddPlacePowerNegativeUncommon(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_NEGATIVE_UNCOMMON
    BONUS = AddPlacePowerNegativeCommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerNegativeRare(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_NEGATIVE_RARE
    BONUS = AddPlacePowerNegativeUncommon.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerNegativeEpic(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_NEGATIVE_EPIC
    BONUS = AddPlacePowerNegativeRare.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class AddPlacePowerNegativeLegendary(AddPlacePowerBase):
    TYPE = relations.CARD_TYPE.ADD_PLACE_POWER_NEGATIVE_LEGENDARY
    BONUS = AddPlacePowerNegativeEpic.BONUS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class HelpPlaceBase(BaseEffect):
    TYPE = None
    HELPS = None

    @property
    def DESCRIPTION(self):
        if self.HELPS != 1:
            return 'В документах города появляются дополнительные записи о помощи, полученной от героя в количестве %(helps)d шт.' % {'helps': self.HELPS}
        return 'В документах города появляется дополнительная запись о помощи, полученной от героя.'

    @property
    def success_message(self):
        if self.HELPS != 1:
            return 'Герою записано %(helps)d дополнительных фактов помощи городу.' % {'helps': self.HELPS}
        return 'Герою записан один дополнительный факт помощи городу.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        place_id = task.data.get('place_id')

        if place_id not in places_storage.places:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Город не найден.')

        for i in range(self.HELPS):
            task.hero.places_history.add_place(place_id)

        storage.save_bundle_data(bundle_id=task.hero.actions.current_action.bundle_id)

        return task.logic_result()


class HelpPlaceUncommon(HelpPlaceBase):
    TYPE = relations.CARD_TYPE.MOST_COMMON_PLACES_UNCOMMON
    HELPS = 1

class HelpPlaceRare(HelpPlaceBase):
    TYPE = relations.CARD_TYPE.MOST_COMMON_PLACES_RARE
    HELPS =  HelpPlaceUncommon.HELPS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class HelpPlaceEpic(HelpPlaceBase):
    TYPE = relations.CARD_TYPE.MOST_COMMON_PLACES_EPIC
    HELPS =  HelpPlaceRare.HELPS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class HelpPlaceLegendary(HelpPlaceBase):
    TYPE = relations.CARD_TYPE.MOST_COMMON_PLACES_LEGENDARY
    HELPS =  HelpPlaceEpic.HELPS * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class ShortTeleport(BaseEffect):
    TYPE = relations.CARD_TYPE.SHORT_TELEPORT

    DESCRIPTION = 'Телепортирует героя до ближайшего города либо до ближайшей ключевой точки задания. Работает только во время движения по дорогам.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        if not task.hero.actions.current_action.TYPE.is_MOVE_TO:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Герой не находится в движении.')

        if not task.hero.actions.current_action.teleport_to_place(create_inplace_action=True):
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Телепортировать героя не получилось.')

        return task.logic_result()


class LongTeleport(BaseEffect):
    TYPE = relations.CARD_TYPE.LONG_TELEPORT

    DESCRIPTION = 'Телепортирует героя в конечную точку назначения либо до ближайшей ключевой точки задания. Работает только во время движения по дорогам.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if not task.hero.actions.current_action.TYPE.is_MOVE_TO:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Герой не находится в движении.')

        if not task.hero.actions.current_action.teleport_to_end():
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Телепортировать героя не получилось.')

        return task.logic_result()


class ExperienceToEnergyBase(BaseEffect):
    TYPE = None
    EXPERIENCE = None

    @property
    def DESCRIPTION(self):
        return 'Преобразует опыт героя на текущем уровне в дополнительную энергию по курсу %(experience)s опыта за 1 энергии.' % {'experience': self.EXPERIENCE}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if task.hero.experience == 0:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет свободного опыта.')

        energy = task.hero.convert_experience_to_energy(self.EXPERIENCE)

        return task.logic_result(message='Герой потерял весь накопленный опыт. Вы получили %(energy)d энергии.' % {'energy': energy})


class ExperienceToEnergyUncommon(ExperienceToEnergyBase):
    TYPE = relations.CARD_TYPE.EXPERIENCE_TO_ENERGY_UNCOMMON
    EXPERIENCE = 7

class ExperienceToEnergyRare(ExperienceToEnergyBase):
    TYPE = relations.CARD_TYPE.EXPERIENCE_TO_ENERGY_RARE
    EXPERIENCE = 6

class ExperienceToEnergyEpic(ExperienceToEnergyBase):
    TYPE = relations.CARD_TYPE.EXPERIENCE_TO_ENERGY_EPIC
    EXPERIENCE = 5

class ExperienceToEnergyLegendary(ExperienceToEnergyBase):
    TYPE = relations.CARD_TYPE.EXPERIENCE_TO_ENERGY_LEGENDARY
    EXPERIENCE = 4


class SharpRandomArtifact(BaseEffect):
    TYPE = relations.CARD_TYPE.SHARP_RANDOM_ARTIFACT
    DESCRIPTION = 'Улучшает случайный артефакт из экипировки героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        artifact = random.choice(list(task.hero.equipment.values()))

        distribution=task.hero.preferences.archetype.power_distribution
        min_power, max_power = Power.artifact_power_interval(distribution, task.hero.level)

        artifact.sharp(distribution=distribution,
                       max_power=max_power,
                       force=True)

        return task.logic_result(message='Улучшена экипировка героя: %(artifact)s' % {'artifact': artifact.html_label()})



class SharpAllArtifacts(BaseEffect):
    TYPE = relations.CARD_TYPE.SHARP_ALL_ARTIFACTS
    DESCRIPTION = 'Улучшает все артефакты из экипировки героя.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        for artifact in list(task.hero.equipment.values()):
            distribution=task.hero.preferences.archetype.power_distribution
            min_power, max_power = Power.artifact_power_interval(distribution, task.hero.level)

            artifact.sharp(distribution=distribution,
                           max_power=max_power,
                           force=True)

        return task.logic_result(message='Вся экипировка героя улучшена')


class GetCompanionBase(BaseEffect):
    TYPE = None
    RARITY = None

    @property
    def DESCRIPTION(self):
        return 'Герой получает спутника, указанного в названии карты. Если у героя уже есть спутник, он покинет героя.'


    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613
        card = task.hero.cards.get_card(task.data['card_uid'])

        companion = companions_logic.create_companion(companions_storage.companions[card.data['companion_id']])

        task.hero.set_companion(companion)

        return task.logic_result(message='Поздравляем! Ваш герой получил нового спутника.')

    @classmethod
    def get_available_companions(cls):
        available_companions = [companion
                                for companion in companions_storage.companions.enabled_companions()
                                if companion.rarity == cls.RARITY and companion.mode.is_AUTOMATIC]
        return available_companions

    def create_card(self, available_for_auction, companion=None):
        if companion is None:
            available_companions = self.get_available_companions()
            companion = random.choice(available_companions)

        return objects.Card(type=self.TYPE, available_for_auction=available_for_auction, data={'companion_id': companion.id})

    @classmethod
    def available(cls):
        return bool(cls.get_available_companions())


    def name_for_card(self, card):
        return self.TYPE.text + ': ' + companions_storage.companions[card.data['companion_id']].name


class GetCompanionCommon(GetCompanionBase):
    TYPE = relations.CARD_TYPE.GET_COMPANION_COMMON
    RARITY = companions_relations.RARITY.COMMON

class GetCompanionUncommon(GetCompanionBase):
    TYPE = relations.CARD_TYPE.GET_COMPANION_UNCOMMON
    RARITY = companions_relations.RARITY.UNCOMMON

class GetCompanionRare(GetCompanionBase):
    TYPE = relations.CARD_TYPE.GET_COMPANION_RARE
    RARITY = companions_relations.RARITY.RARE

class GetCompanionEpic(GetCompanionBase):
    TYPE = relations.CARD_TYPE.GET_COMPANION_EPIC
    RARITY = companions_relations.RARITY.EPIC

class GetCompanionLegendary(GetCompanionBase):
    TYPE = relations.CARD_TYPE.GET_COMPANION_LEGENDARY
    RARITY = companions_relations.RARITY.LEGENDARY



class ReleaseCompanion(BaseEffect):
    TYPE = relations.CARD_TYPE.RELEASE_COMPANION
    DESCRIPTION = 'Спутник героя навсегда покидает его.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if task.hero.companion is None:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя сейчас нет спутника.')

        task.hero.add_message('companions_left', diary=True, companion_owner=task.hero, companion=task.hero.companion)
        task.hero.remove_companion()

        return task.logic_result(message='Поздравляем! Ваш герой получил нового спутника.')



class HealCompanionBase(BaseEffect):
    TYPE = None
    HEALTH = None

    @property
    def DESCRIPTION(self):
        return 'Восстанавливает спутнику %(health)d здоровья.' % {'health': self.HEALTH}

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        if task.hero.companion is None:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет спутника.')

        if task.hero.companion.health == task.hero.companion.max_health:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='Спутник героя полностью здоров.')

        health = task.hero.companion.heal(self.HEALTH)

        return task.logic_result(message='Спутник вылечен на %(health)s HP.' % {'health': health})


class HealCompanionCommon(HealCompanionBase):
    TYPE = relations.CARD_TYPE.HEAL_COMPANION_COMMON
    HEALTH = 10

class HealCompanionUncommon(HealCompanionBase):
    TYPE = relations.CARD_TYPE.HEAL_COMPANION_UNCOMMON
    HEALTH = HealCompanionCommon.HEALTH * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class HealCompanionRare(HealCompanionBase):
    TYPE = relations.CARD_TYPE.HEAL_COMPANION_RARE
    HEALTH = HealCompanionUncommon.HEALTH * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class HealCompanionEpic(HealCompanionBase):
    TYPE = relations.CARD_TYPE.HEAL_COMPANION_EPIC
    HEALTH = HealCompanionRare.HEALTH * (c.CARDS_COMBINE_TO_UP_RARITY + 1)

class HealCompanionLegendary(HealCompanionBase):
    TYPE = relations.CARD_TYPE.HEAL_COMPANION_LEGENDARY
    HEALTH = HealCompanionEpic.HEALTH * (c.CARDS_COMBINE_TO_UP_RARITY + 1)


class UpgradeArtifact(BaseEffect):
    TYPE = relations.CARD_TYPE.INCREMENT_ARTIFACT_RARITY
    DESCRIPTION = 'Заменяет случайный экипированный не эпический артефакт, на более редкий того же вида.'

    def use(self, task, storage, **kwargs): # pylint: disable=R0911,W0613

        artifacts = [artifact for artifact in list(task.hero.equipment.values()) if not artifact.rarity.is_EPIC]

        if not artifacts:
            return task.logic_result(next_step=UseCardTask.STEP.ERROR, message='У героя нет экипированных не эпических артефактов.')

        artifact = random.choice(artifacts)

        task.hero.increment_equipment_rarity(artifact)

        return task.logic_result(message='Качество артефакта %(artifact)s улучшено.' % {'artifact': artifact.html_label()})



EFFECTS = {card_class.TYPE: card_class()
           for card_class in discovering.discover_classes(globals().values(), BaseEffect)
           if card_class.TYPE is not None}


PREFERENCE_RESET_CARDS = {card_class.PREFERENCE: card_class()
                          for card_class in discovering.discover_classes(globals().values(), PreferencesCooldownsResetBase)}

HABIT_POINTS_CARDS = {card_class.TYPE: card_class()
                      for card_class in discovering.discover_classes(globals().values(), ChangeHabitBase)}

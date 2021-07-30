#!/usr/bin/env python3
# pylint: disable=bad-whitespace
# pylint: disable=too-many-return-statements

CMD_ARGS = {
    'ALL': {
        'pi': [],
        'say': [str,],
        'l': [int,int,int,int,],
        'displ_bright': [int],
        'glcd_text': [int,int,int,str],
        'glcd_dialog': [str],
        'glcd_draw': [int,int,int,str],
        'uc': [],
        'ud': [],
        'a': [int,str,int,str,float,float,float,int,int,],
        'd': [int,],
        'g': [int],
        's': [int,float],
        'ncp': [int,int],
        'is': [int,int,int,int,int,str,str,],
        'b': [int,int],
        'bn': [str,],
        'bd': [int],
        'ba': [int,int,str,],
        'br': [int,int,int],
        'p': [int,int,int],
        'pn': [str,],
        'pb': [int,str],
        'pr': [],
        'ps': [],
        'psa': [str,],
        'pcl': [],
        'pbd': [int,int],
        'sr': [int,int],
        'ssg': [int,int],
        'sn': [str,],
        'ssl': [int],
        'sss': [],
        'ssa': [str,],
        'ssd': [int],
        'ts': [float,str,int],
        'tn': [],
        'tf': [],
        'ti': [int],
        'restore': [],
        'r': [int,],
        'c': [int,int,],
        'upr': [int],
        'ups': [int],
        'lp': [int],
        'reset_eeprom': [],
        'enc_clicked': [int],
        'enc_left': [int],
        'enc_right': [int],
        'button_clicked': [int],
        'pot_call_check': [int],
        'pot_call_ok': [int],
        'control_skip_enable': [],
        'control_bad_skip': [],
        'save_pot_cal': [int,int],
        'sys_gio': [int,int,float],
        'sys_ghp': [float],
        'sys_ngc': [int],
        'sys_ngt': [int],
        'sys_ngd': [int],
        'sys_cmm': [int],
        'sys_cmr': [int],
        'sys_pbg': [int],
        'sys_ams': [],
        'sys_bts': [],
        'sys_btd': [],
        'sys_ctl': [str],
        'sys_ver': [str],
        'sys_ser': [],
        'sys_usb': [int],
        'sys_mnr': [int],
        'sys_rbt': [],
        'sys_led': [int,int,],
        'sys_nam': [int,str],
        'sys_uni': [int,str],
        'sys_val': [int,str],
        'sys_ind': [int,float],
        'sys_pch': [int],
        'sys_spc': [int],
    },
    'DUO': {
        'boot': [int,int,str,],
        'fn': [int],
        'bc': [int,int],
        'n': [int],
        'si': [int,int,int],
    },
    'DUOX': {
        'boot': [int,int,str,],
        'ss': [int],
        'sl': [int],
        'sc': [],
        'pa': [int,int,int,int,int,int],
        's_contrast': [int,int],
        'exp_overcurrent': [],
    },
    'DWARF': {
        'cs': [int,int],
        'pa': [int,int,int,int,int,int,int,int],
    },
}

CMD_PING                          = 'pi'
CMD_SAY                           = 'say'
CMD_LED                           = 'l'
CMD_DISP_BRIGHTNESS               = 'displ_bright'
CMD_GLCD_TEXT                     = 'glcd_text'
CMD_GLCD_DIALOG                   = 'glcd_dialog'
CMD_GLCD_DRAW                     = 'glcd_draw'
CMD_GUI_CONNECTED                 = 'uc'
CMD_GUI_DISCONNECTED              = 'ud'
CMD_CONTROL_ADD                   = 'a'
CMD_CONTROL_REMOVE                = 'd'
CMD_CONTROL_GET                   = 'g'
CMD_CONTROL_SET                   = 's'
CMD_CONTROL_PAGE                  = 'ncp'
CMD_INITIAL_STATE                 = 'is'
CMD_BANKS                         = 'b'
CMD_BANK_NEW                      = 'bn'
CMD_BANK_DELETE                   = 'bd'
CMD_ADD_PBS_TO_BANK               = 'ba'
CMD_REORDER_PBS_IN_BANK           = 'br'
CMD_PEDALBOARDS                   = 'p'
CMD_PEDALBOARD_NAME_SET           = 'pn'
CMD_PEDALBOARD_LOAD               = 'pb'
CMD_PEDALBOARD_RESET              = 'pr'
CMD_PEDALBOARD_SAVE               = 'ps'
CMD_PEDALBOARD_SAVE_AS            = 'psa'
CMD_PEDALBOARD_CLEAR              = 'pcl'
CMD_PEDALBOARD_DELETE             = 'pbd'
CMD_REORDER_SSS_IN_PB             = 'sr'
CMD_SNAPSHOTS                     = 'ssg'
CMD_SNAPSHOT_NAME_SET             = 'sn'
CMD_SNAPSHOTS_LOAD                = 'ssl'
CMD_SNAPSHOTS_SAVE                = 'sss'
CMD_SNAPSHOT_SAVE_AS              = 'ssa'
CMD_SNAPSHOT_DELETE               = 'ssd'
CMD_TUNER                         = 'ts'
CMD_TUNER_ON                      = 'tn'
CMD_TUNER_OFF                     = 'tf'
CMD_TUNER_INPUT                   = 'ti'
CMD_RESTORE                       = 'restore'
CMD_RESPONSE                      = 'r'
CMD_MENU_ITEM_CHANGE              = 'c'
CMD_PROFILE_LOAD                  = 'upr'
CMD_PROFILE_STORE                 = 'ups'
CMD_NEXT_PAGE                     = 'lp'
CMD_RESET_EEPROM                  = 'reset_eeprom'
CMD_SELFTEST_ENCODER_CLICKED      = 'enc_clicked'
CMD_SELFTEST_ENCODER_LEFT         = 'enc_left'
CMD_SELFTEST_ENCODER_RIGHT        = 'enc_right'
CMD_SELFTEST_BUTTON_CLICKED       = 'button_clicked'
CMD_SELFTEST_CHECK_CALIBRATION    = 'pot_call_check'
CMD_SELFTEST_CALLIBRATION_OK      = 'pot_call_ok'
CMD_SELFTEST_SKIP_CONTROL_ENABLE  = 'control_skip_enable'
CMD_SELFTEST_SKIP_CONTROL         = 'control_bad_skip'
CMD_SELFTEST_SAVE_POT_CALIBRATION = 'save_pot_cal'
CMD_SYS_GAIN                      = 'sys_gio'
CMD_SYS_HP_GAIN                   = 'sys_ghp'
CMD_SYS_NG_CHANNEL                = 'sys_ngc'
CMD_SYS_NG_THRESHOLD              = 'sys_ngt'
CMD_SYS_NG_DECAY                  = 'sys_ngd'
CMD_SYS_COMP_MODE                 = 'sys_cmm'
CMD_SYS_COMP_RELEASE              = 'sys_cmr'
CMD_SYS_COMP_PEDALBOARD_GAIN      = 'sys_pbg'
CMD_SYS_AMIXER_SAVE               = 'sys_ams'
CMD_SYS_BT_STATUS                 = 'sys_bts'
CMD_SYS_BT_DISCOVERY              = 'sys_btd'
CMD_SYS_SYSTEMCTL                 = 'sys_ctl'
CMD_SYS_VERSION                   = 'sys_ver'
CMD_SYS_SERIAL                    = 'sys_ser'
CMD_SYS_USB_MODE                  = 'sys_usb'
CMD_SYS_NOISE_REMOVAL             = 'sys_mnr'
CMD_SYS_REBOOT                    = 'sys_rbt'
CMD_SYS_CHANGE_LED                = 'sys_led'
CMD_SYS_CHANGE_NAME               = 'sys_nam'
CMD_SYS_CHANGE_UNIT               = 'sys_uni'
CMD_SYS_CHANGE_VALUE              = 'sys_val'
CMD_SYS_CHANGE_WIDGET_INDICATOR   = 'sys_ind'
CMD_SYS_PAGE_CHANGE               = 'sys_pch'
CMD_SYS_SUBPAGE_CHANGE            = 'sys_spc'
CMD_DUO_BOOT                      = 'boot'
CMD_DUO_FOOT_NAVIG                = 'fn'
CMD_DUO_BANK_CONFIG               = 'bc'
CMD_DUO_CONTROL_NEXT              = 'n'
CMD_DUO_CONTROL_INDEX_SET         = 'si'
CMD_DUOX_BOOT                     = 'boot'
CMD_DUOX_SNAPSHOT_SAVE            = 'ss'
CMD_DUOX_SNAPSHOT_LOAD            = 'sl'
CMD_DUOX_SNAPSHOT_CLEAR           = 'sc'
CMD_DUOX_PAGES_AVAILABLE          = 'pa'
CMD_DUOX_SET_CONTRAST             = 's_contrast'
CMD_DUOX_EXP_OVERCURRENT          = 'exp_overcurrent'
CMD_DWARF_CONTROL_SUBPAGE         = 'cs'
CMD_DWARF_PAGES_AVAILABLE         = 'pa'

BANK_FUNC_NONE            = 0
BANK_FUNC_TRUE_BYPASS     = 1
BANK_FUNC_PEDALBOARD_NEXT = 2
BANK_FUNC_PEDALBOARD_PREV = 3
BANK_FUNC_COUNT           = 4

FLAG_CONTROL_BYPASS           = 0x001
FLAG_CONTROL_TAP_TEMPO        = 0x002
FLAG_CONTROL_ENUMERATION      = 0x004
FLAG_CONTROL_SCALE_POINTS     = 0x008
FLAG_CONTROL_TRIGGER          = 0x010
FLAG_CONTROL_TOGGLED          = 0x020
FLAG_CONTROL_LOGARITHMIC      = 0x040
FLAG_CONTROL_INTEGER          = 0x080
FLAG_CONTROL_REVERSE          = 0x100
FLAG_CONTROL_MOMENTARY        = 0x200

FLAG_PAGINATION_PAGE_UP       = 0x1
FLAG_PAGINATION_WRAP_AROUND   = 0x2
FLAG_PAGINATION_INITIAL_REQ   = 0x4
FLAG_PAGINATION_ALT_LED_COLOR = 0x8

FLAG_SCALEPOINT_PAGINATED     = 0x1
FLAG_SCALEPOINT_WRAP_AROUND   = 0x2
FLAG_SCALEPOINT_END_PAGE      = 0x4
FLAG_SCALEPOINT_ALT_LED_COLOR = 0x8

MENU_ID_SL_IN            = 0
MENU_ID_SL_OUT           = 1
MENU_ID_TUNER_MUTE       = 2
MENU_ID_QUICK_BYPASS     = 3
MENU_ID_PLAY_STATUS      = 4
MENU_ID_MIDI_CLK_SOURCE  = 5
MENU_ID_MIDI_CLK_SEND    = 6
MENU_ID_SNAPSHOT_PRGCHGE = 7
MENU_ID_PB_PRGCHNGE      = 8
MENU_ID_TEMPO            = 9
MENU_ID_BEATS_PER_BAR    = 10
MENU_ID_BYPASS1          = 11
MENU_ID_BYPASS2          = 12
MENU_ID_BRIGHTNESS       = 13
MENU_ID_CURRENT_PROFILE  = 14
MENU_ID_FOOTSWITCH_NAV   = 30
MENU_ID_EXP_CV_INPUT     = 40
MENU_ID_HP_CV_OUTPUT     = 41
MENU_ID_MASTER_VOL_PORT  = 42
MENU_ID_EXP_MODE         = 43
MENU_ID_TOP              = 44

def menu_item_id_to_str(idx):
    if not isinstance(idx, int):
        raise ValueError
    if idx == 0:
        return "MENU_ID_SL_IN"
    if idx == 1:
        return "MENU_ID_SL_OUT"
    if idx == 2:
        return "MENU_ID_TUNER_MUTE"
    if idx == 3:
        return "MENU_ID_QUICK_BYPASS"
    if idx == 4:
        return "MENU_ID_PLAY_STATUS"
    if idx == 5:
        return "MENU_ID_MIDI_CLK_SOURCE"
    if idx == 6:
        return "MENU_ID_MIDI_CLK_SEND"
    if idx == 7:
        return "MENU_ID_SNAPSHOT_PRGCHGE"
    if idx == 8:
        return "MENU_ID_PB_PRGCHNGE"
    if idx == 9:
        return "MENU_ID_TEMPO"
    if idx == 10:
        return "MENU_ID_BEATS_PER_BAR"
    if idx == 11:
        return "MENU_ID_BYPASS1"
    if idx == 12:
        return "MENU_ID_BYPASS2"
    if idx == 13:
        return "MENU_ID_BRIGHTNESS"
    if idx == 14:
        return "MENU_ID_CURRENT_PROFILE"
    if idx == 30:
        return "MENU_ID_FOOTSWITCH_NAV"
    if idx == 40:
        return "MENU_ID_EXP_CV_INPUT"
    if idx == 41:
        return "MENU_ID_HP_CV_OUTPUT"
    if idx == 42:
        return "MENU_ID_MASTER_VOL_PORT"
    if idx == 43:
        return "MENU_ID_EXP_MODE"
    if idx == 44:
        return "MENU_ID_TOP"
    return "unknown"

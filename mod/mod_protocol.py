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
        'ncp': [int,int,int],
        'is': [int,int,int,int,int,int,str,str,],
        'b': [int,int],
        'bn': [str,],
        'bd': [int],
        'ba': [int,int,str,],
        'br': [int,int,int],
        'p': [int,int,int],
        'pn': [str,],
        'pchng': [int],
        'pb': [int,str],
        'pr': [],
        'ps': [],
        'psa': [str,],
        'pcl': [],
        'pbd': [int,int],
        'sr': [int,int],
        'ssg': [int,int],
        'sn': [int,str,],
        'ssl': [int],
        'sss': [],
        'ssa': [str,],
        'ssd': [int],
        'ts': [float,str,int],
        'tn': [],
        'tf': [],
        'ti': [int],
        'tr': [int],
        'restore': [],
        'screenshot': [int,str],
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
        'sys_cvi': [int],
        'sys_exp': [int],
        'sys_cvo': [int],
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
        'sys_lbl': [int,int,int,int],
        'sys_lbh': [int,int,int],
        'sys_nam': [int,str],
        'sys_uni': [int,str],
        'sys_val': [int,str],
        'sys_ind': [int,float],
        'sys_pop': [int,int,str,str],
        'sys_pch': [int],
        'sys_spc': [int],
    },
    'DUO': {
        'boot': [int,int,str,],
        'fn': [int],
        'bc': [int,int],
        'n': [int],
        'si': [int,int,int],
        'ncp': [int,int], # Backwards compat for Duo and Duo X
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
CMD_PEDALBOARD_CHANGE             = 'pchng'
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
CMD_TUNER_REF_FREQ                = 'tr'
CMD_RESTORE                       = 'restore'
CMD_SCREENSHOT                    = 'screenshot'
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
CMD_SYS_CVI_MODE                  = 'sys_cvi'
CMD_SYS_EXP_MODE                  = 'sys_exp'
CMD_SYS_CVO_MODE                  = 'sys_cvo'
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
CMD_SYS_CHANGE_LED_BLINK          = 'sys_lbl'
CMD_SYS_CHANGE_LED_BRIGHTNESS     = 'sys_lbh'
CMD_SYS_CHANGE_NAME               = 'sys_nam'
CMD_SYS_CHANGE_UNIT               = 'sys_uni'
CMD_SYS_CHANGE_VALUE              = 'sys_val'
CMD_SYS_CHANGE_WIDGET_INDICATOR   = 'sys_ind'
CMD_SYS_LAUNCH_POPUP              = 'sys_pop'
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

FLAG_NAVIGATION_FACTORY       = 0x1
FLAG_NAVIGATION_READ_ONLY     = 0x2
FLAG_NAVIGATION_DIVIDER       = 0x4
FLAG_NAVIGATION_TRIAL_PLUGINS = 0x8

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

def cmd_to_str(cmd):
    if not isinstance(cmd, str):
        raise ValueError
    if cmd == "pi":
        return "CMD_PING"
    if cmd == "say":
        return "CMD_SAY"
    if cmd == "l":
        return "CMD_LED"
    if cmd == "displ_bright":
        return "CMD_DISP_BRIGHTNESS"
    if cmd == "glcd_text":
        return "CMD_GLCD_TEXT"
    if cmd == "glcd_dialog":
        return "CMD_GLCD_DIALOG"
    if cmd == "glcd_draw":
        return "CMD_GLCD_DRAW"
    if cmd == "uc":
        return "CMD_GUI_CONNECTED"
    if cmd == "ud":
        return "CMD_GUI_DISCONNECTED"
    if cmd == "a":
        return "CMD_CONTROL_ADD"
    if cmd == "d":
        return "CMD_CONTROL_REMOVE"
    if cmd == "g":
        return "CMD_CONTROL_GET"
    if cmd == "s":
        return "CMD_CONTROL_SET"
    if cmd == "ncp":
        return "CMD_CONTROL_PAGE"
    if cmd == "is":
        return "CMD_INITIAL_STATE"
    if cmd == "b":
        return "CMD_BANKS"
    if cmd == "bn":
        return "CMD_BANK_NEW"
    if cmd == "bd":
        return "CMD_BANK_DELETE"
    if cmd == "ba":
        return "CMD_ADD_PBS_TO_BANK"
    if cmd == "br":
        return "CMD_REORDER_PBS_IN_BANK"
    if cmd == "p":
        return "CMD_PEDALBOARDS"
    if cmd == "pn":
        return "CMD_PEDALBOARD_NAME_SET"
    if cmd == "pchng":
        return "CMD_PEDALBOARD_CHANGE"
    if cmd == "pb":
        return "CMD_PEDALBOARD_LOAD"
    if cmd == "pr":
        return "CMD_PEDALBOARD_RESET"
    if cmd == "ps":
        return "CMD_PEDALBOARD_SAVE"
    if cmd == "psa":
        return "CMD_PEDALBOARD_SAVE_AS"
    if cmd == "pcl":
        return "CMD_PEDALBOARD_CLEAR"
    if cmd == "pbd":
        return "CMD_PEDALBOARD_DELETE"
    if cmd == "sr":
        return "CMD_REORDER_SSS_IN_PB"
    if cmd == "ssg":
        return "CMD_SNAPSHOTS"
    if cmd == "sn":
        return "CMD_SNAPSHOT_NAME_SET"
    if cmd == "ssl":
        return "CMD_SNAPSHOTS_LOAD"
    if cmd == "sss":
        return "CMD_SNAPSHOTS_SAVE"
    if cmd == "ssa":
        return "CMD_SNAPSHOT_SAVE_AS"
    if cmd == "ssd":
        return "CMD_SNAPSHOT_DELETE"
    if cmd == "ts":
        return "CMD_TUNER"
    if cmd == "tn":
        return "CMD_TUNER_ON"
    if cmd == "tf":
        return "CMD_TUNER_OFF"
    if cmd == "ti":
        return "CMD_TUNER_INPUT"
    if cmd == "tr":
        return "CMD_TUNER_REF_FREQ"
    if cmd == "restore":
        return "CMD_RESTORE"
    if cmd == "screenshot":
        return "CMD_SCREENSHOT"
    if cmd == "r":
        return "CMD_RESPONSE"
    if cmd == "c":
        return "CMD_MENU_ITEM_CHANGE"
    if cmd == "upr":
        return "CMD_PROFILE_LOAD"
    if cmd == "ups":
        return "CMD_PROFILE_STORE"
    if cmd == "lp":
        return "CMD_NEXT_PAGE"
    if cmd == "reset_eeprom":
        return "CMD_RESET_EEPROM"
    if cmd == "enc_clicked":
        return "CMD_SELFTEST_ENCODER_CLICKED"
    if cmd == "enc_left":
        return "CMD_SELFTEST_ENCODER_LEFT"
    if cmd == "enc_right":
        return "CMD_SELFTEST_ENCODER_RIGHT"
    if cmd == "button_clicked":
        return "CMD_SELFTEST_BUTTON_CLICKED"
    if cmd == "pot_call_check":
        return "CMD_SELFTEST_CHECK_CALIBRATION"
    if cmd == "pot_call_ok":
        return "CMD_SELFTEST_CALLIBRATION_OK"
    if cmd == "control_skip_enable":
        return "CMD_SELFTEST_SKIP_CONTROL_ENABLE"
    if cmd == "control_bad_skip":
        return "CMD_SELFTEST_SKIP_CONTROL"
    if cmd == "save_pot_cal":
        return "CMD_SELFTEST_SAVE_POT_CALIBRATION"
    if cmd == "sys_gio":
        return "CMD_SYS_GAIN"
    if cmd == "sys_ghp":
        return "CMD_SYS_HP_GAIN"
    if cmd == "sys_cvi":
        return "CMD_SYS_CVI_MODE"
    if cmd == "sys_exp":
        return "CMD_SYS_EXP_MODE"
    if cmd == "sys_cvo":
        return "CMD_SYS_CVO_MODE"
    if cmd == "sys_ngc":
        return "CMD_SYS_NG_CHANNEL"
    if cmd == "sys_ngt":
        return "CMD_SYS_NG_THRESHOLD"
    if cmd == "sys_ngd":
        return "CMD_SYS_NG_DECAY"
    if cmd == "sys_cmm":
        return "CMD_SYS_COMP_MODE"
    if cmd == "sys_cmr":
        return "CMD_SYS_COMP_RELEASE"
    if cmd == "sys_pbg":
        return "CMD_SYS_COMP_PEDALBOARD_GAIN"
    if cmd == "sys_ams":
        return "CMD_SYS_AMIXER_SAVE"
    if cmd == "sys_bts":
        return "CMD_SYS_BT_STATUS"
    if cmd == "sys_btd":
        return "CMD_SYS_BT_DISCOVERY"
    if cmd == "sys_ctl":
        return "CMD_SYS_SYSTEMCTL"
    if cmd == "sys_ver":
        return "CMD_SYS_VERSION"
    if cmd == "sys_ser":
        return "CMD_SYS_SERIAL"
    if cmd == "sys_usb":
        return "CMD_SYS_USB_MODE"
    if cmd == "sys_mnr":
        return "CMD_SYS_NOISE_REMOVAL"
    if cmd == "sys_rbt":
        return "CMD_SYS_REBOOT"
    if cmd == "sys_lbl":
        return "CMD_SYS_CHANGE_LED_BLINK"
    if cmd == "sys_lbh":
        return "CMD_SYS_CHANGE_LED_BRIGHTNESS"
    if cmd == "sys_nam":
        return "CMD_SYS_CHANGE_NAME"
    if cmd == "sys_uni":
        return "CMD_SYS_CHANGE_UNIT"
    if cmd == "sys_val":
        return "CMD_SYS_CHANGE_VALUE"
    if cmd == "sys_ind":
        return "CMD_SYS_CHANGE_WIDGET_INDICATOR"
    if cmd == "sys_pop":
        return "CMD_SYS_LAUNCH_POPUP"
    if cmd == "sys_pch":
        return "CMD_SYS_PAGE_CHANGE"
    if cmd == "sys_spc":
        return "CMD_SYS_SUBPAGE_CHANGE"
    if cmd == "boot":
        return "CMD_DUO_BOOT"
    if cmd == "fn":
        return "CMD_DUO_FOOT_NAVIG"
    if cmd == "bc":
        return "CMD_DUO_BANK_CONFIG"
    if cmd == "n":
        return "CMD_DUO_CONTROL_NEXT"
    if cmd == "si":
        return "CMD_DUO_CONTROL_INDEX_SET"
    if cmd == "boot":
        return "CMD_DUOX_BOOT"
    if cmd == "ss":
        return "CMD_DUOX_SNAPSHOT_SAVE"
    if cmd == "sl":
        return "CMD_DUOX_SNAPSHOT_LOAD"
    if cmd == "sc":
        return "CMD_DUOX_SNAPSHOT_CLEAR"
    if cmd == "pa":
        return "CMD_DUOX_PAGES_AVAILABLE"
    if cmd == "s_contrast":
        return "CMD_DUOX_SET_CONTRAST"
    if cmd == "exp_overcurrent":
        return "CMD_DUOX_EXP_OVERCURRENT"
    if cmd == "cs":
        return "CMD_DWARF_CONTROL_SUBPAGE"
    if cmd == "pa":
        return "CMD_DWARF_PAGES_AVAILABLE"
    return "unknown"

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

from tests.common.utilities import wait_until
from tests.common.helpers.assertions import pytest_assert
from tests.common.helpers.ntp_helper import check_ntp_status, run_ntp, setup_ntp_context
import logging
import time
import pytest


logger = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.disable_loganalyzer,
    pytest.mark.topology('any'),
    pytest.mark.device_type('vs')
]

TIME_FORWARD = 3600


def pytest_generate_tests(metafunc):
    if "ptf_use_ipv6" in metafunc.fixturenames:
        metafunc.parametrize("ptf_use_ipv6", [False, True], scope="module")


def config_long_jump(duthost, enable=False):
    """change ntpd option to enable or disable long jump"""
    ntpsec_conf_stat = duthost.stat(path="/etc/ntpsec/ntp.conf")
    using_ntpsec = ntpsec_conf_stat["stat"]["exists"]
    if enable:
        logger.info("enable ntp long jump")
        if using_ntpsec:
            regex = "s/NTPD_OPTS=\\\"-x -N\\\"/NTPD_OPTS=\\\"-g -N\\\"/"
        else:
            regex = "s/NTPD_OPTS='-x'/NTPD_OPTS='-g'/"
    else:
        logger.info("disable ntp long jump")
        if using_ntpsec:
            regex = "s/NTPD_OPTS=\\\"-g -N\\\"/NTPD_OPTS=\\\"-x -N\\\"/"
        else:
            regex = "s/NTPD_OPTS='-g'/NTPD_OPTS='-x'/"

    if using_ntpsec:
        duthost.command("sudo sed -i '%s' /etc/default/ntpsec" % regex)
    else:
        duthost.command("sudo sed -i %s /etc/default/ntp" % regex)
    duthost.service(name='ntp', state='restarted')


@pytest.fixture(scope="module")
def setup_ntp(ptfhost, duthosts, rand_one_dut_hostname, ptf_use_ipv6):
    if ptf_use_ipv6 and not ptfhost.mgmt_ipv6:
        pytest.skip("No IPv6 address on PTF host")
    with setup_ntp_context(ptfhost, duthosts[rand_one_dut_hostname], ptf_use_ipv6) as result:
        yield result


@pytest.fixture
def setup_long_jump_config(duthosts, rand_one_dut_hostname):
    """set long jump config and set DUT's time forward"""

    duthost = duthosts[rand_one_dut_hostname]

    # collect long jump state
    long_jump_enable = False
    if not duthost.shell("grep -q \"NTPD_OPTS='-g'\" /etc/default/ntp", module_ignore_errors=True)['rc']:
        long_jump_enable = True
    if not duthost.shell("grep -q \"NTPD_OPTS=\\\"-g -N\\\"\" /etc/default/ntpsec", module_ignore_errors=True)['rc']:
        long_jump_enable = True

    # get time before set time
    start_time_dut = int(duthost.command("date +%s")['stdout'])
    start_time = time.time()

    # stop NTP and set time on DUT
    duthost.service(name='ntp', state='stopped')
    duthost.command("date -s '@{}'".format(start_time_dut - TIME_FORWARD))

    # set long jump config with variable
    yield

    # set DUT's time back after long jump test
    duthost.service(name='ntp', state='stopped')
    dut_end_time = int(time.time()) - int(start_time) + start_time_dut
    duthost.command("date -s '@{}'".format(dut_end_time))
    config_long_jump(duthost, long_jump_enable)


def test_ntp_long_jump_enabled(duthosts, rand_one_dut_hostname, setup_ntp, setup_long_jump_config):
    duthost = duthosts[rand_one_dut_hostname]

    config_long_jump(duthost, enable=True)

    pytest_assert(wait_until(720, 10, 0, check_ntp_status, duthost),
                  "NTP long jump enable failed")


def test_ntp_long_jump_disabled(duthosts, rand_one_dut_hostname, setup_ntp, setup_long_jump_config):
    duthost = duthosts[rand_one_dut_hostname]

    config_long_jump(duthost, enable=False)

    pytest_assert(wait_until(720, 10, 0, check_ntp_status, duthost),
                  "NTP long jump disable failed")


def test_ntp(duthosts, rand_one_dut_hostname, setup_ntp):
    run_ntp(duthosts[rand_one_dut_hostname])

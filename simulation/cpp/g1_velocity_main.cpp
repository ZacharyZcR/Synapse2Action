#include "FSM/CtrlFSM.h"
#include "FSM/State_RLBase.h"
#include "Types.h"
#include "isaaclab/envs/mdp/observations/observations.h"
#include "unitree/dds_wrapper/robots/go2/go2_sub.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <mutex>

static std::shared_ptr<unitree::robot::go2::subscription::SportModeState> odometry;

namespace isaaclab::mdp
{
REGISTER_OBSERVATION(sim_velocity_commands)
{
    static const char* target_value = std::getenv("S2A_TARGET_X_M");
    static const float target_x = target_value == nullptr ? 0.0f : std::stof(target_value);
    static const float maximum_speed = [] {
        const char* value = std::getenv("S2A_MAX_SPEED_MPS");
        return value == nullptr ? 0.3f : std::stof(value);
    }();
    if (target_value == nullptr || odometry->isTimeout()) {
        return std::vector<float>{0.0f, 0.0f, 0.0f};
    }
    std::lock_guard<std::mutex> lock(odometry->mutex_);
    const float error = target_x - odometry->msg_.position()[0];
    const float speed = std::clamp(std::abs(0.8f * error), 0.2f, maximum_speed);
    const float command = std::abs(error) <= 0.05f
        ? 0.0f
        : std::copysign(speed, error);
    return std::vector<float>{command, 0.0f, 0.0f};
}
}

std::unique_ptr<LowCmd_t> FSMState::lowcmd = nullptr;
std::shared_ptr<LowState_t> FSMState::lowstate = nullptr;
std::shared_ptr<Keyboard> FSMState::keyboard = std::make_shared<Keyboard>();

int main(int argc, char** argv)
{
    auto vm = param::helper(argc, argv);
    FSMStringMap.insert({1, "Passive"});
    FSMStringMap.insert({3, "Velocity"});

    unitree::robot::ChannelFactory::Instance()->Init(1, vm["network"].as<std::string>());
    FSMState::lowcmd = std::make_unique<LowCmd_t>();
    FSMState::lowstate = std::make_shared<LowState_t>();
    odometry = std::make_shared<unitree::robot::go2::subscription::SportModeState>();
    FSMState::lowstate->wait_for_connection();
    odometry->wait_for_connection();
    FSMState::lowcmd->msg_.mode_machine() = 5;

    auto velocity = std::make_shared<State_RLBase>(3, "Velocity");
    auto fsm = std::make_unique<CtrlFSM>(velocity);
    fsm->start();
    while (true) sleep(1);
}

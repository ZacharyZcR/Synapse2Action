#include "FSM/CtrlFSM.h"
#include "FSM/State_RLBase.h"
#include "Types.h"
#include "isaaclab/envs/mdp/observations/observations.h"

#include <cstdlib>

namespace isaaclab::mdp
{
REGISTER_OBSERVATION(sim_velocity_commands)
{
    static const float forward_mps = [] {
        const char* value = std::getenv("S2A_FORWARD_MPS");
        return value == nullptr ? 0.0f : std::stof(value);
    }();
    static int policy_step = 0;
    const bool moving = policy_step >= 50 && policy_step < 350;
    ++policy_step;
    return std::vector<float>{moving ? forward_mps : 0.0f, 0.0f, 0.0f};
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
    FSMState::lowstate->wait_for_connection();
    FSMState::lowcmd->msg_.mode_machine() = 5;

    auto velocity = std::make_shared<State_RLBase>(3, "Velocity");
    auto fsm = std::make_unique<CtrlFSM>(velocity);
    fsm->start();
    while (true) sleep(1);
}

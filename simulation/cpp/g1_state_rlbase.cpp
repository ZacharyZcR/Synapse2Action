#include "FSM/State_RLBase.h"
#include "unitree_articulation.h"
#include "isaaclab/envs/mdp/observations/observations.h"
#include "isaaclab/envs/mdp/actions/joint_actions.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <unordered_map>

namespace isaaclab
{
REGISTER_OBSERVATION(keyboard_velocity_commands)
{
    std::string key = FSMState::keyboard->key();
    static std::unordered_map<std::string, std::vector<float>> key_commands = {
        {"w", {1.0f, 0.0f, 0.0f}}, {"s", {-1.0f, 0.0f, 0.0f}},
        {"a", {0.0f, 1.0f, 0.0f}}, {"d", {0.0f, -1.0f, 0.0f}},
        {"q", {0.0f, 0.0f, 1.0f}}, {"e", {0.0f, 0.0f, -1.0f}},
    };
    const auto found = key_commands.find(key);
    return found == key_commands.end() ? std::vector<float>{0.0f, 0.0f, 0.0f} : found->second;
}
}

State_RLBase::State_RLBase(int state_mode, std::string state_string)
: FSMState(state_mode, state_string)
{
    auto cfg = param::config["FSM"][state_string];
    auto policy_dir = param::parser_policy_dir(cfg["policy_dir"].as<std::string>());
    env = std::make_unique<isaaclab::ManagerBasedRLEnv>(
        YAML::LoadFile(policy_dir / "params" / "deploy.yaml"),
        std::make_shared<unitree::BaseArticulation<LowState_t::SharedPtr>>(FSMState::lowstate)
    );
    env->alg = std::make_unique<isaaclab::OrtRunner>(policy_dir / "exported" / "policy.onnx");
    registered_checks.emplace_back(std::make_pair(
        [&]()->bool { return isaaclab::mdp::bad_orientation(env.get(), 1.0); },
        FSMStringMap.right.at("Passive")
    ));
}

namespace
{
using Pose = std::array<float, 9>;
constexpr std::array<int, 9> joints = {12, 15, 16, 17, 18, 22, 23, 24, 25};
constexpr Pose stand = {0.0f, 0.0f, 0.25f, 0.0f, 0.97f, 0.0f, -0.25f, 0.0f, 0.97f};
constexpr Pose grasp = {0.0f, -0.36445f, -0.02471f, 0.78152f, 1.45247f, -0.36455f, 0.02455f, -0.78133f, 1.45280f};
constexpr Pose lift = {0.0f, 0.17811f, 0.46812f, -0.37733f, -0.36836f, 0.17808f, -0.46815f, 0.37730f, -0.36835f};
constexpr Pose transport = {0.0f, -0.21138f, 0.44107f, 0.14765f, 0.97303f, 0.17808f, -0.46815f, 0.37730f, -0.36835f};

Pose interpolate(const Pose& from, const Pose& to, float ratio)
{
    ratio = std::clamp(ratio, 0.0f, 1.0f);
    ratio = ratio * ratio * (3.0f - 2.0f * ratio);
    Pose result{};
    for (std::size_t i = 0; i < result.size(); ++i) result[i] = from[i] + (to[i] - from[i]) * ratio;
    return result;
}

Pose manipulation_pose(float seconds)
{
    static const float time_scale = [] {
        const char* value = std::getenv("S2A_MANIPULATION_TIME_SCALE");
        return value == nullptr ? 1.0f : std::clamp(std::stof(value), 0.5f, 1.5f);
    }();
    seconds /= time_scale;
    if (seconds < 1.0f) return stand;
    if (seconds < 5.0f) return interpolate(stand, grasp, (seconds - 1.0f) / 4.0f);
    if (seconds < 9.0f) return interpolate(grasp, lift, (seconds - 5.0f) / 4.0f);
    if (seconds < 12.0f) return interpolate(lift, transport, (seconds - 9.0f) / 3.0f);
    return transport;
}
}

void State_RLBase::run()
{
    auto action = env->action_manager->processed_actions();
    for (int i = 0; i < env->robot->data.joint_ids_map.size(); ++i) {
        lowcmd->msg_.motor_cmd()[env->robot->data.joint_ids_map[i]].q() = action[i];
    }
    if (std::getenv("S2A_PICK_PLACE") == nullptr) return;
    static const auto started = std::chrono::steady_clock::now();
    const float seconds = std::chrono::duration<float>(std::chrono::steady_clock::now() - started).count();
    const auto pose = manipulation_pose(seconds);
    for (std::size_t i = 0; i < joints.size(); ++i) lowcmd->msg_.motor_cmd()[joints[i]].q() = pose[i];
}

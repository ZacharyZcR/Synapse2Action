#include "FSM/State_RLBase.h"
#include "unitree_articulation.h"
#include "isaaclab/envs/mdp/observations/observations.h"
#include "isaaclab/envs/mdp/actions/joint_actions.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <sstream>
#include <stdexcept>
#include <type_traits>
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
using JointMap = std::array<int, 9>;
using PhaseTimes = std::array<float, 4>;

template <typename T, std::size_t N>
std::array<T, N> environment_array(const char* name)
{
    const char* value = std::getenv(name);
    if (value == nullptr) throw std::runtime_error(std::string("missing ") + name);
    std::array<T, N> result{};
    std::stringstream stream(value);
    std::string item;
    for (std::size_t index = 0; index < N; ++index) {
        if (!std::getline(stream, item, ',')) throw std::runtime_error(std::string("invalid ") + name);
        if constexpr (std::is_same_v<T, int>) result[index] = std::stoi(item);
        else result[index] = std::stof(item);
    }
    if (std::getline(stream, item, ',')) throw std::runtime_error(std::string("invalid ") + name);
    return result;
}

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
    static const Pose stand = environment_array<float, 9>("S2A_MANIPULATION_STAND");
    static const Pose grasp = environment_array<float, 9>("S2A_MANIPULATION_GRASP");
    static const Pose lift = environment_array<float, 9>("S2A_MANIPULATION_LIFT");
    static const Pose transport = environment_array<float, 9>("S2A_MANIPULATION_TRANSPORT");
    static const PhaseTimes phases = environment_array<float, 4>("S2A_MANIPULATION_PHASE_END_SECONDS");
    static const float time_scale = [] {
        const char* value = std::getenv("S2A_MANIPULATION_TIME_SCALE");
        return value == nullptr ? 1.0f : std::clamp(std::stof(value), 0.5f, 1.5f);
    }();
    static const float start_delay = [] {
        const char* value = std::getenv("S2A_MANIPULATION_START_DELAY_SECONDS");
        return value == nullptr ? 0.0f : std::clamp(std::stof(value), 0.0f, 60.0f);
    }();
    seconds = std::max(0.0f, seconds - start_delay);
    seconds /= time_scale;
    if (seconds < phases[0]) return stand;
    if (seconds < phases[1]) return interpolate(stand, grasp, (seconds - phases[0]) / (phases[1] - phases[0]));
    if (seconds < phases[2]) return interpolate(grasp, lift, (seconds - phases[1]) / (phases[2] - phases[1]));
    if (seconds < phases[3]) return interpolate(lift, transport, (seconds - phases[2]) / (phases[3] - phases[2]));
    return transport;
}
}

void State_RLBase::run()
{
    auto action = env->action_manager->processed_actions();
    for (int i = 0; i < env->robot->data.joint_ids_map.size(); ++i) {
        lowcmd->msg_.motor_cmd()[env->robot->data.joint_ids_map[i]].q() = action[i];
    }
    if (std::getenv("S2A_TASK_TRAJECTORY") == nullptr) return;
    static const auto started = std::chrono::steady_clock::now();
    const float seconds = std::chrono::duration<float>(std::chrono::steady_clock::now() - started).count();
    const auto pose = manipulation_pose(seconds);
    static const JointMap joints = environment_array<int, 9>("S2A_MANIPULATION_JOINTS");
    for (std::size_t i = 0; i < joints.size(); ++i) lowcmd->msg_.motor_cmd()[joints[i]].q() = pose[i];
}

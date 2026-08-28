#include "FSM/CtrlFSM.h"
#include "FSM/State_RLBase.h"
#include "Types.h"
#include "isaaclab/envs/mdp/observations/observations.h"
#include "unitree/dds_wrapper/robots/go2/go2_sub.h"
#include <spdlog/spdlog.h>

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
    static const float target_y = [] {
        const char* value = std::getenv("S2A_TARGET_Y_M");
        return value == nullptr ? 0.0f : std::stof(value);
    }();
    static const float target_yaw = [] {
        const char* value = std::getenv("S2A_TARGET_YAW_RAD");
        return value == nullptr ? 0.0f : std::stof(value);
    }();
    static const float maximum_speed = [] {
        const char* value = std::getenv("S2A_MAX_SPEED_MPS");
        return value == nullptr ? 0.3f : std::stof(value);
    }();
    static const bool avoid_obstacle = std::getenv("S2A_OBSTACLE_X_M") != nullptr;
    static const float obstacle_x = avoid_obstacle ? std::stof(std::getenv("S2A_OBSTACLE_X_M")) : 0.0f;
    static const float obstacle_y = avoid_obstacle ? std::stof(std::getenv("S2A_OBSTACLE_Y_M")) : 0.0f;
    static const float obstacle_radius = avoid_obstacle ? std::stof(std::getenv("S2A_OBSTACLE_RADIUS_M")) : 0.0f;
    static int waypoint_stage = avoid_obstacle ? 0 : 2;
    static bool replan_logged = false;
    if (target_value == nullptr || odometry->isTimeout()) {
        return std::vector<float>{0.0f, 0.0f, 0.0f};
    }
    std::lock_guard<std::mutex> lock(odometry->mutex_);
    const float position_x = odometry->msg_.position()[0];
    const float position_y = odometry->msg_.position()[1];
    const float waypoint_x = waypoint_stage == 0 ? 0.0f : obstacle_x + obstacle_radius + 0.20f;
    const float waypoint_y = obstacle_y + obstacle_radius + 0.45f;
    if (waypoint_stage < 2 && !replan_logged) {
        spdlog::info("Navigation replan: two-waypoint detour");
        replan_logged = true;
    }
    if (waypoint_stage < 2 && std::hypot(waypoint_x - position_x, waypoint_y - position_y) <= 0.08f) {
        ++waypoint_stage;
        spdlog::info("Navigation waypoint {} reached", waypoint_stage);
    }
    const float active_target_x = waypoint_stage < 2
        ? (waypoint_stage == 0 ? 0.0f : obstacle_x + obstacle_radius + 0.20f)
        : target_x;
    const float active_target_y = waypoint_stage < 2 ? waypoint_y : target_y;
    const float world_x = active_target_x - position_x;
    const float world_y = active_target_y - position_y;
    const float distance = std::hypot(world_x, world_y);
    const float yaw = odometry->msg_.imu_state().rpy()[2];
    const float body_x = std::cos(yaw) * world_x + std::sin(yaw) * world_y;
    const float body_y = -std::sin(yaw) * world_x + std::cos(yaw) * world_y;
    float vx = 0.0f;
    float vy = 0.0f;
    if (distance > 0.05f) {
        const float speed = std::clamp(0.8f * distance, 0.2f, maximum_speed);
        vx = speed * body_x / distance;
        vy = speed * body_y / distance;
    }
    const float yaw_error = std::atan2(
        std::sin(target_yaw - yaw),
        std::cos(target_yaw - yaw)
    );
    const float yaw_rate = std::abs(yaw_error) <= 0.05f
        ? 0.0f
        : std::clamp(1.2f * yaw_error, -0.2f, 0.2f);
    return std::vector<float>{vx, vy, yaw_rate};
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

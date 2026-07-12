#include "rclcpp/rclcpp.hpp"

class MyNode : public rclcpp::Node //MODIFY NAME
{
public:
    MyNode() : Node("node_name")//MODIFY NAEM
    {
    }
private:
};

int main(int argc,char **argv)
{
    rclcpp::init(argc,argv);
    auto node = std::make_shared<MyNode>();//MODIFY NAME
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
DrCOM 802.1X
=====

H3C 的 802.1X 认证已有现成的代码

我没有看白皮书，估计情况不同在需要认证的步数，和认证的内容上有别，其他估计一样。<br>
应该是在 *Identity* 区附加了 *DrCOM* 的认证数据

本项目 fork 自 http://github.com/humiaozuzu/YaH3C

目前只作为测试使用, 根据原作者的声明

    YaH3c的代码使用MIT License发布，此外，禁止使用YaH3C以及YaH3C的修改程序用于商业目的（比如交叉编译到路由进行销售等行为）

如果最后 **使用该代码** 作为 *DrCOM* 登陆脚本的 802.1X 模块， 则
集成了 802.1X 协议的客户端将不允许进行商业目的(比如路由器厂家集成)。

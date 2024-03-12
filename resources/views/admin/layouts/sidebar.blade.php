<aside id="sidebar" class="sidebar">

    <ul class="sidebar-nav" id="sidebar-nav">

        <li class="nav-item">
            <a class="nav-link " href="{{ route('admin.menu.index') }}">
                <i class="bi bi-grid"></i>
                <span>Bosh sahifa</span>
            </a>
        </li>
        @if(\Illuminate\Support\Facades\Auth::user()->role == 1)
            <li class="nav-item">
            <a class="nav-link " href="{{ route('admin.users.index') }}">
                <i class="bi bi-grid"></i>
                <span>Mahsulot Toifalari</span>
            </a>
        </li>
        @endif

{{--        <li class="nav-item">--}}
{{--            <a class="nav-link " href="{{ route('admin.menu.index') }}">--}}
{{--                <i class="bi bi-grid"></i>--}}
{{--                <span>Mahsulotlar</span>--}}
{{--            </a>--}}
{{--        </li>--}}
        <!-- End Dashboard Nav -->


{{--        <li class="nav-heading">Pages</li>--}}

{{--        <li class="nav-item">--}}
{{--            <a class="nav-link collapsed" href="users-profile.html">--}}
{{--                <i class="bi bi-person"></i>--}}
{{--                <span>Profile</span>--}}
{{--            </a>--}}
{{--        </li><!-- End Profile Page Nav -->--}}



{{--        <li class="nav-item">--}}
{{--            <a class="nav-link collapsed" href="pages-register.html">--}}
{{--                <i class="bi bi-card-list"></i>--}}
{{--                <span>Register</span>--}}
{{--            </a>--}}
{{--        </li><!-- End Register Page Nav -->--}}

{{--        <li class="nav-item">--}}
{{--            <a class="nav-link collapsed" href="pages-login.html">--}}
{{--                <i class="bi bi-box-arrow-in-right"></i>--}}
{{--                <span>Login</span>--}}
{{--            </a>--}}
{{--        </li><!-- End Login Page Nav -->--}}



    </ul>

</aside><!-- End Sidebar-->

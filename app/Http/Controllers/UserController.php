<?php

namespace App\Http\Controllers;

use App\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;

class UserController extends Controller
{
    public function index()
    {
        $users = User::all();
        return view('admin.users.index')->with('users',$users);

    }

    public function create()
    {
        $regions=Region::all();
        return view('admin.users.create',['regions'=>$regions]);
    }

    public function store(Request $request)
    {

        $password=Hash::make($request->password);
        User::create([
            'name' => $request->name,
            'email' =>$request->email,
            'password' => $password,
            'role'=>$request->role,
        ]);
        return redirect()->route('admin.users.index');
    }

    public function show($id)
    {
        //
    }

    public function edit(User $user)
    {
        $regions=Region::all();
        return view('admin.users.edit',compact('user','regions'));
    }

    public function update(Request $request, User $user)
    {
        $request->validate([
            'name' => 'required',
            'email' => 'required',
            'password' => 'required|confirmed|min:8',

        ]);

        $user->update([
            'name'=>$request->name,
            'email'=>$request->email,
            'password'=>Hash::make($request->password),
            'role'=>$request->role,
        ]);
        return redirect()->route('admin.users.index')
            ->with('success','Успешно Обновлено');
    }

    public function destroy(User $user)
    {
        $user->delete();
        return redirect()->back();
    }
}
